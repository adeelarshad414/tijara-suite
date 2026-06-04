from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tijara_bridge import __version__
from tijara_bridge.drivers import build_driver_output


SERVICE_NAME = "tijara-hardware-bridge"
MAX_BODY_BYTES = 1024 * 1024
SIGNATURE_SKEW_SECONDS = 300


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BridgeConfig:
    host: str
    port: int
    shared_secret: str
    dry_run: bool
    device_config_path: Path
    job_dir: Path
    require_known_device: bool

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        return cls(
            host=os.environ.get("TIJARA_BRIDGE_HOST", "0.0.0.0"),
            port=int(os.environ.get("TIJARA_BRIDGE_PORT", "9109")),
            shared_secret=os.environ.get("TIJARA_BRIDGE_SHARED_SECRET", ""),
            dry_run=env_bool("TIJARA_BRIDGE_DRY_RUN", True),
            device_config_path=Path(
                os.environ.get(
                    "TIJARA_BRIDGE_DEVICE_CONFIG",
                    "/etc/tijara-bridge/devices.json",
                )
            ),
            job_dir=Path(os.environ.get("TIJARA_BRIDGE_JOB_DIR", "/var/lib/tijara-bridge/jobs")),
            require_known_device=env_bool("TIJARA_BRIDGE_REQUIRE_KNOWN_DEVICE", False),
        )


def load_devices(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    devices = raw.get("devices", raw if isinstance(raw, list) else [])
    result: dict[str, dict[str, Any]] = {}
    for device in devices:
        code = device.get("code") or device.get("device_code")
        if code:
            result[str(code)] = device
    return result


class BridgeState:
    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.devices = load_devices(config.device_config_path)
        config.job_dir.mkdir(parents=True, exist_ok=True)

    @property
    def capabilities(self) -> list[str]:
        return [
            "health",
            "signed_requests",
            "dry_run_jobs",
            "receipt_print",
            "label_print",
            "cash_drawer",
            "customer_display",
            "scale_read",
            "scanner_event",
            "escpos_bytes",
            "zpl_bytes",
            "cups_submission",
            "raw_tcp_delivery",
            "cash_drawer_pulse",
            "display_state_delivery",
        ]

    def write_job(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = f"tjbr-{uuid.uuid4().hex}"
        device_code = str(payload.get("device_code") or "")
        device = self.devices.get(device_code)
        result = {
            "service": SERVICE_NAME,
            "version": __version__,
            "status": "accepted",
            "job_id": job_id,
            "operation": operation,
            "device_code": device_code or False,
            "device_configured": bool(device),
            "dry_run": self.config.dry_run,
            "driver_status": "queued_dry_run" if self.config.dry_run else "queued_for_driver",
            "created_at": int(time.time()),
        }
        if device:
            result["device_type"] = device.get("type") or device.get("device_type")
            result["driver"] = device.get("driver", "dry_run")
        driver_output = build_driver_output(operation, payload, device, self.config.dry_run)
        if driver_output:
            result["driver_output_format"] = driver_output["format"]
            result["driver_output_bytes"] = driver_output["byte_count"]
            delivery = driver_output.get("delivery") or {}
            if delivery.get("status"):
                result["driver_status"] = delivery["status"]
            if delivery.get("transport"):
                result["driver_transport"] = delivery["transport"]
            if driver_output.get("reading"):
                result.update(driver_output["reading"])

        job_path = self.config.job_dir / f"{job_id}.json"
        with job_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {"result": result, "payload": payload, "driver_output": driver_output},
                handle,
                indent=2,
                ensure_ascii=False,
            )
        return result


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Tijara-Bridge-Version", __version__)
    handler.end_headers()
    handler.wfile.write(body)


def make_signature(secret: str, timestamp: str, body: bytes) -> str:
    message = timestamp.encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = f"{SERVICE_NAME}/{__version__}"

    @property
    def state(self) -> BridgeState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/health":
            return json_response(
                self,
                200,
                {
                    "service": SERVICE_NAME,
                    "version": __version__,
                    "status": "ok",
                    "dry_run": self.state.config.dry_run,
                    "device_count": len(self.state.devices),
                    "devices": sorted(self.state.devices),
                    "capabilities": self.state.capabilities,
                },
            )
        return json_response(self, 404, {"status": "error", "message": "Unknown endpoint"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        body = self._read_body()
        if body is None:
            return
        if not self._verify_signature(body):
            return

        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError as error:
            return json_response(self, 400, {"status": "error", "message": str(error)})

        endpoints = {
            "/v1/test": "test",
            "/v1/print/receipt": "print_receipt",
            "/v1/print/label": "print_label",
            "/v1/cash-drawer/open": "open_cash_drawer",
            "/v1/display/customer": "customer_display",
            "/v1/scale/read": "read_scale",
            "/v1/scan/event": "scanner_event",
        }
        operation = endpoints.get(path)
        if not operation:
            return json_response(self, 404, {"status": "error", "message": "Unknown endpoint"})

        device_code = str(payload.get("device_code") or "")
        device = self.state.devices.get(device_code)
        if device and device.get("enabled") is False:
            return json_response(
                self,
                409,
                {"status": "error", "message": f"Device {device_code} is disabled"},
            )
        if self.state.config.require_known_device and device_code and not device:
            return json_response(
                self,
                404,
                {"status": "error", "message": f"Device {device_code} is not configured"},
            )

        response = self.state.write_job(operation, payload)
        if operation == "read_scale":
            response.setdefault("weight", payload.get("test_weight", 0))
            response.setdefault("unit", payload.get("unit", "kg"))
        return json_response(self, 202, response)

    def _read_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length") or "0")
        if length > MAX_BODY_BYTES:
            json_response(self, 413, {"status": "error", "message": "Payload too large"})
            return None
        return self.rfile.read(length)

    def _verify_signature(self, body: bytes) -> bool:
        secret = self.state.config.shared_secret
        if not secret:
            json_response(
                self,
                401,
                {"status": "error", "message": "Bridge shared secret is not configured"},
            )
            return False

        timestamp = self.headers.get("X-Tijara-Timestamp", "")
        supplied = self.headers.get("X-Tijara-Signature", "")
        if not timestamp or not supplied:
            json_response(self, 401, {"status": "error", "message": "Missing signature headers"})
            return False

        try:
            request_time = int(timestamp)
        except ValueError:
            json_response(self, 401, {"status": "error", "message": "Invalid timestamp"})
            return False
        if abs(int(time.time()) - request_time) > SIGNATURE_SKEW_SECONDS:
            json_response(self, 401, {"status": "error", "message": "Signature timestamp expired"})
            return False

        expected = make_signature(secret, timestamp, body)
        supplied = supplied.removeprefix("sha256=")
        if not hmac.compare_digest(expected, supplied):
            json_response(self, 401, {"status": "error", "message": "Invalid signature"})
            return False
        return True


class BridgeServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], state: BridgeState) -> None:
        super().__init__(server_address, BridgeHandler)
        self.state = state


def main() -> None:
    config = BridgeConfig.from_env()
    state = BridgeState(config)
    server = BridgeServer((config.host, config.port), state)
    print(
        json.dumps(
            {
                "service": SERVICE_NAME,
                "version": __version__,
                "host": config.host,
                "port": config.port,
                "dry_run": config.dry_run,
                "device_count": len(state.devices),
                "secret_configured": bool(config.shared_secret),
            },
            separators=(",", ":"),
        )
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
