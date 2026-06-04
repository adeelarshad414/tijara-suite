from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any


def escpos_receipt_bytes(payload: dict[str, Any]) -> bytes:
    """Build a conservative ESC/POS byte stream for dry-run receipt jobs."""
    text = str(payload.get("ticket_text") or payload.get("payload") or "")
    if not text.strip():
        text = "Tijara receipt print job"
    normalized = "\n".join(line.rstrip() for line in text.splitlines())
    encoded = normalized.encode("utf-8", errors="replace")
    initialize = b"\x1b@"
    line_spacing = b"\x1b3\x18"
    cut = b"\n\n\x1dV\x00"
    return initialize + line_spacing + encoded + cut


def zpl_label_bytes(payload: dict[str, Any]) -> bytes:
    zpl = str(
        payload.get("zpl")
        or payload.get("label_zpl")
        or payload.get("payload")
        or "^XA^FO50,50^A0N,30,30^FDTijara Label^FS^XZ"
    )
    return zpl.encode("utf-8", errors="replace")


def cash_drawer_pulse_bytes(payload: dict[str, Any]) -> bytes:
    pin = int(payload.get("cash_drawer_pin") or 0)
    on_time = int(payload.get("pulse_on_time") or 25)
    off_time = int(payload.get("pulse_off_time") or 250)
    return bytes([0x1B, 0x70, pin, max(0, min(on_time, 255)), max(0, min(off_time, 255))])


def compact_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def device_setting(device: dict[str, Any] | None, payload: dict[str, Any], *names: str):
    config = payload.get("device_config") if isinstance(payload.get("device_config"), dict) else {}
    for name in names:
        if payload.get(name) not in (None, ""):
            return payload.get(name)
        if config.get(name) not in (None, ""):
            return config.get(name)
        if (device or {}).get(name) not in (None, ""):
            return (device or {}).get(name)
    return None


def driver_name(device: dict[str, Any] | None, payload: dict[str, Any]) -> str:
    return str(device_setting(device, payload, "driver", "driver_name") or "dry_run")


def persist_output_file(data: bytes, payload: dict[str, Any], device: dict[str, Any] | None, suffix: str):
    output_file = device_setting(device, payload, "output_file")
    if not output_file:
        output_dir = os.environ.get("TIJARA_BRIDGE_OUTPUT_DIR")
        if not output_dir:
            return None
        code = str(payload.get("device_code") or "device")
        output_file = str(Path(output_dir) / f"{code}-{int(time.time())}.{suffix}")
    path = Path(str(output_file))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def send_raw_tcp(data: bytes, payload: dict[str, Any], device: dict[str, Any] | None):
    host = device_setting(device, payload, "tcp_host", "host", "ip_address")
    port = device_setting(device, payload, "tcp_port", "port")
    if not host or not port:
        return None
    timeout = float(device_setting(device, payload, "timeout_seconds") or 5)
    with socket.create_connection((str(host), int(port)), timeout=timeout) as sock:
        sock.sendall(data)
    return {"host": str(host), "port": int(port)}


def submit_cups(data: bytes, payload: dict[str, Any], device: dict[str, Any] | None):
    printer_name = device_setting(device, payload, "cups_printer", "printer_name", "queue")
    if not printer_name:
        return None
    command = ["lp", "-d", str(printer_name)]
    title = device_setting(device, payload, "job_title")
    if title:
        command.extend(["-t", str(title)])
    result = subprocess.run(
        command,
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "printer": str(printer_name),
        "returncode": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="replace").strip(),
        "stderr": result.stderr.decode("utf-8", errors="replace").strip(),
    }


def read_scale(payload: dict[str, Any], device: dict[str, Any] | None):
    host = device_setting(device, payload, "scale_host", "tcp_host", "host", "ip_address")
    port = device_setting(device, payload, "scale_port", "tcp_port", "port")
    unit = str(payload.get("unit") or device_setting(device, payload, "unit") or "kg")
    if not host or not port:
        return {"weight": float(payload.get("test_weight") or 0), "unit": unit, "source": "dry_run"}
    timeout = float(device_setting(device, payload, "timeout_seconds") or 5)
    command = device_setting(device, payload, "scale_command")
    with socket.create_connection((str(host), int(port)), timeout=timeout) as sock:
        if command:
            sock.sendall(str(command).encode("ascii", errors="ignore"))
        raw = sock.recv(128).decode("ascii", errors="ignore").strip()
    number = "".join(ch for ch in raw if ch.isdigit() or ch in ".-")
    return {
        "weight": float(number) if number else 0.0,
        "unit": unit,
        "raw": raw,
        "source": "tcp_scale",
    }


def deliver_bytes(
    data: bytes,
    payload: dict[str, Any],
    device: dict[str, Any] | None,
    suffix: str,
    dry_run: bool,
):
    if dry_run:
        return {"status": "dry_run"}

    cups_result = submit_cups(data, payload, device)
    if cups_result:
        return {
            "status": "submitted" if cups_result["returncode"] == 0 else "driver_error",
            "transport": "cups",
            "cups": cups_result,
        }

    tcp_result = send_raw_tcp(data, payload, device)
    if tcp_result:
        return {"status": "submitted", "transport": "raw_tcp", "target": tcp_result}

    output_path = persist_output_file(data, payload, device, suffix)
    if output_path:
        return {"status": "submitted", "transport": "file", "path": str(output_path)}

    return {
        "status": "driver_not_configured",
        "message": "Set cups_printer, tcp_host/tcp_port, or output_file for non-dry-run delivery.",
    }


def output_payload(
    fmt: str,
    data: bytes,
    payload: dict[str, Any],
    device: dict[str, Any] | None,
    suffix: str,
    dry_run: bool,
):
    delivery = deliver_bytes(data, payload, device, suffix, dry_run)
    return {
        "format": fmt,
        "bytes_base64": base64.b64encode(data).decode("ascii"),
        "byte_count": len(data),
        "driver": driver_name(device, payload),
        "delivery": delivery,
    }


def build_driver_output(
    operation: str,
    payload: dict[str, Any],
    device: dict[str, Any] | None,
    dry_run: bool = True,
):
    printer_language = (
        payload.get("printer_language")
        or (device or {}).get("printer_language")
        or payload.get("device_config", {}).get("printer_language")
    )
    if operation == "print_receipt" and printer_language == "escpos":
        output = escpos_receipt_bytes(payload)
        return output_payload("escpos_base64", output, payload, device, "escpos", dry_run)
    if operation == "print_receipt" and printer_language == "cups":
        output = escpos_receipt_bytes(payload)
        return output_payload("cups_text_base64", output, payload, device, "txt", dry_run)
    if operation == "print_label":
        output = zpl_label_bytes(payload)
        return output_payload("zpl_base64", output, payload, device, "zpl", dry_run)
    if operation == "open_cash_drawer":
        output = cash_drawer_pulse_bytes(payload)
        return output_payload("escpos_cash_drawer_base64", output, payload, device, "bin", dry_run)
    if operation == "customer_display":
        output = compact_json_bytes(payload)
        return output_payload("customer_display_json_base64", output, payload, device, "json", dry_run)
    if operation == "scanner_event":
        output = compact_json_bytes(payload)
        return output_payload("scanner_event_json_base64", output, payload, device, "json", dry_run)
    if operation == "read_scale":
        reading = read_scale(payload, device) if not dry_run else {
            "weight": float(payload.get("test_weight") or 0),
            "unit": payload.get("unit") or "kg",
            "source": "dry_run",
        }
        return {
            "format": "scale_reading",
            "driver": driver_name(device, payload),
            "delivery": {"status": "read" if not dry_run else "dry_run"},
            "reading": reading,
            "byte_count": 0,
        }
    return False
