#!/usr/bin/env python3
"""Generate Tijara Grafana dashboard provisioning JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT_DIR / "deploy/monitoring/grafana/dashboards"
DS_PROMETHEUS = {"type": "prometheus", "uid": "prometheus"}
GRID_W = 24


def target(expr: str, legend: str = "", ref_id: str = "A") -> dict:
    payload = {
        "datasource": DS_PROMETHEUS,
        "editorMode": "code",
        "expr": expr,
        "instant": False,
        "legendFormat": legend,
        "range": True,
        "refId": ref_id,
    }
    return payload


def field_config(unit: str = "short", decimals: Optional[int] = None, thresholds: Optional[list] = None) -> dict:
    defaults = {
        "color": {"mode": "thresholds"},
        "mappings": [],
        "thresholds": thresholds
        or {
            "mode": "absolute",
            "steps": [
                {"color": "green", "value": None},
                {"color": "orange", "value": 1},
                {"color": "red", "value": 5},
            ],
        },
        "unit": unit,
    }
    if decimals is not None:
        defaults["decimals"] = decimals
    return {"defaults": defaults, "overrides": []}


def stat_panel(panel_id: int, title: str, expr: str, grid: dict, unit: str = "short", decimals: Optional[int] = None) -> dict:
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "datasource": DS_PROMETHEUS,
        "gridPos": grid,
        "targets": [target(expr)],
        "fieldConfig": field_config(unit, decimals),
        "options": {
            "colorMode": "value",
            "graphMode": "area",
            "justifyMode": "auto",
            "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "auto",
            "wideLayout": True,
        },
    }


def timeseries_panel(panel_id: int, title: str, queries: list[tuple[str, str]], grid: dict, unit: str = "short") -> dict:
    return {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "datasource": DS_PROMETHEUS,
        "gridPos": grid,
        "targets": [target(expr, legend, chr(ord("A") + index)) for index, (expr, legend) in enumerate(queries)],
        "fieldConfig": field_config(unit),
        "options": {
            "legend": {"calcs": ["lastNotNull"], "displayMode": "table", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }


def bar_panel(panel_id: int, title: str, expr: str, legend: str, grid: dict, unit: str = "short") -> dict:
    return {
        "id": panel_id,
        "type": "bargauge",
        "title": title,
        "datasource": DS_PROMETHEUS,
        "gridPos": grid,
        "targets": [target(expr, legend)],
        "fieldConfig": field_config(unit),
        "options": {
            "displayMode": "gradient",
            "maxVizHeight": 300,
            "minVizHeight": 16,
            "minVizWidth": 8,
            "namePlacement": "auto",
            "orientation": "horizontal",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "showUnfilled": True,
            "sizing": "auto",
            "valueMode": "color",
        },
    }


def table_panel(panel_id: int, title: str, queries: list[tuple[str, str]], grid: dict, unit: str = "short") -> dict:
    return {
        "id": panel_id,
        "type": "table",
        "title": title,
        "datasource": DS_PROMETHEUS,
        "gridPos": grid,
        "targets": [target(expr, legend, chr(ord("A") + index)) for index, (expr, legend) in enumerate(queries)],
        "fieldConfig": field_config(unit),
        "options": {
            "cellHeight": "sm",
            "footer": {"countRows": False, "fields": "", "reducer": ["sum"], "show": False},
            "showHeader": True,
            "sortBy": [],
        },
    }


def dashboard(uid: str, title: str, tags: list[str], panels: list[dict], description: str) -> dict:
    return {
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "enable": True,
                    "hide": True,
                    "iconColor": "rgba(0, 211, 255, 1)",
                    "name": "Annotations & Alerts",
                    "target": {"limit": 100, "matchAny": False, "tags": [], "type": "dashboard"},
                    "type": "dashboard",
                }
            ]
        },
        "description": description,
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "liveNow": False,
        "panels": panels,
        "refresh": "30s",
        "schemaVersion": 39,
        "style": "dark",
        "tags": tags,
        "templating": {"list": []},
        "time": {"from": "now-24h", "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": title,
        "uid": uid,
        "version": 1,
        "weekStart": "",
    }


def owner_ops_dashboard() -> dict:
    panels = [
        stat_panel(1, "Odoo Availability", 'max(probe_success{job="tijara-http-blackbox",instance=~".*/web/login"})', {"h": 4, "w": 6, "x": 0, "y": 0}, "bool"),
        stat_panel(2, "Business Metrics Scrape", 'max(up{job="tijara-odoo-business"})', {"h": 4, "w": 6, "x": 6, "y": 0}, "bool"),
        stat_panel(3, "Ecommerce Orders", "sum(tijara_ecommerce_orders_total)", {"h": 4, "w": 6, "x": 12, "y": 0}),
        stat_panel(4, "Ecommerce Value PKR", "sum(tijara_ecommerce_order_amount_pkr)", {"h": 4, "w": 6, "x": 18, "y": 0}, "currencyPKR", 0),
        timeseries_panel(5, "Orders By State", [('sum by (state) (tijara_ecommerce_orders_total)', "{{state}}")], {"h": 8, "w": 12, "x": 0, "y": 4}),
        timeseries_panel(6, "Revenue By Payment Status", [('sum by (payment_status) (tijara_ecommerce_order_amount_pkr)', "{{payment_status}}")], {"h": 8, "w": 12, "x": 12, "y": 4}, "currencyPKR"),
        bar_panel(7, "External Assumption Mode", "max by (integration) (tijara_external_assumption_mode)", "{{integration}}", {"h": 8, "w": 12, "x": 0, "y": 12}),
        table_panel(8, "Endpoint Probe Health", [('probe_success{job="tijara-http-blackbox"}', "{{instance}}")], {"h": 8, "w": 12, "x": 12, "y": 12}, "bool"),
    ]
    return dashboard(
        "tijara-owner-ops",
        "Tijara Owner And DevOps Overview",
        ["tijara", "owner", "devops", "operations"],
        panels,
        "Executive and DevOps overview for Odoo availability, ecommerce value, and live integration assumption risks.",
    )


def delivery_dashboard() -> dict:
    panels = [
        stat_panel(1, "Delivery Orders", "sum(tijara_ecommerce_delivery_orders_total)", {"h": 4, "w": 6, "x": 0, "y": 0}),
        stat_panel(2, "Open Critical Exceptions", 'sum(tijara_delivery_open_exceptions{severity="critical"})', {"h": 4, "w": 6, "x": 6, "y": 0}),
        stat_panel(3, "Retry Backlog", "sum(tijara_delivery_retry_pending)", {"h": 4, "w": 6, "x": 12, "y": 0}),
        stat_panel(4, "COD Variance PKR", "sum(tijara_delivery_cod_variance_amount)", {"h": 4, "w": 6, "x": 18, "y": 0}, "currencyPKR", 0),
        timeseries_panel(5, "Delivery Orders By Provider And Status", [('sum by (provider, delivery_status) (tijara_ecommerce_delivery_orders_total)', "{{provider}} / {{delivery_status}}")], {"h": 8, "w": 12, "x": 0, "y": 4}),
        timeseries_panel(6, "Open Exceptions By Provider", [('sum by (provider, severity) (tijara_delivery_open_exceptions)', "{{provider}} / {{severity}}")], {"h": 8, "w": 12, "x": 12, "y": 4}),
        timeseries_panel(7, "Retry Queue Aging", [('max by (provider) (tijara_delivery_retry_oldest_seconds)', "{{provider}}")], {"h": 8, "w": 8, "x": 0, "y": 12}, "s"),
        timeseries_panel(8, "SLA Breach Rate", [('max by (provider) (tijara_delivery_sla_breach_rate_percent)', "{{provider}}")], {"h": 8, "w": 8, "x": 8, "y": 12}, "percent"),
        timeseries_panel(9, "Courier Webhook Failures", [('increase(tijara_delivery_webhook_failures_total[1h])', "{{provider}}")], {"h": 8, "w": 8, "x": 16, "y": 12}),
        table_panel(10, "COD Reconciliation Variance By Provider", [('sum by (provider) (tijara_delivery_cod_variance_amount)', "{{provider}}")], {"h": 8, "w": GRID_W, "x": 0, "y": 20}, "currencyPKR"),
    ]
    return dashboard(
        "tijara-delivery",
        "Tijara Ecommerce And Delivery Operations",
        ["tijara", "ecommerce", "delivery", "courier"],
        panels,
        "Delivery, courier, retries, SLA breaches, webhook failures, ecommerce order handoff, and COD reconciliation.",
    )


def finance_dashboard() -> dict:
    panels = [
        stat_panel(1, "Payment Events", "sum(tijara_payment_events_total)", {"h": 4, "w": 6, "x": 0, "y": 0}),
        stat_panel(2, "Settlement Variance PKR", "sum(tijara_payment_settlement_variance_pkr)", {"h": 4, "w": 6, "x": 6, "y": 0}, "currencyPKR", 0),
        stat_panel(3, "FBR Queue Items", "sum(tijara_fbr_queue_total)", {"h": 4, "w": 6, "x": 12, "y": 0}),
        stat_panel(4, "FBR/PSP Assumption Markers", 'sum(tijara_external_assumption_mode{integration=~"fbr|psp"})', {"h": 4, "w": 6, "x": 18, "y": 0}),
        timeseries_panel(5, "Payment Events By Provider And Status", [('sum by (provider, status, signature_status) (tijara_payment_events_total)', "{{provider}} / {{status}} / {{signature_status}}")], {"h": 8, "w": 12, "x": 0, "y": 4}),
        timeseries_panel(6, "Settlement Variance By Provider", [('sum by (provider, reconciliation_status) (tijara_payment_settlement_variance_pkr)', "{{provider}} / {{reconciliation_status}}")], {"h": 8, "w": 12, "x": 12, "y": 4}, "currencyPKR"),
        timeseries_panel(7, "FBR Queue By State", [('sum by (state, adapter_mode) (tijara_fbr_queue_total)', "{{state}} / {{adapter_mode}}")], {"h": 8, "w": 12, "x": 0, "y": 12}),
        table_panel(8, "FBR Compliance Matrix", [('sum by (certification_environment, compliance_status, adapter_mode) (tijara_fbr_queue_total)', "{{certification_environment}} / {{compliance_status}}")], {"h": 8, "w": 12, "x": 12, "y": 12}),
    ]
    return dashboard(
        "tijara-finance-fbr",
        "Tijara Finance, PSP, And FBR Compliance",
        ["tijara", "finance", "psp", "fbr", "compliance"],
        panels,
        "Finance and compliance dashboard for payment webhooks, settlement variance, FBR queue state, and certification assumptions.",
    )


def hardware_dashboard() -> dict:
    panels = [
        stat_panel(1, "Registered Hardware Devices", "sum(tijara_hardware_devices_total)", {"h": 4, "w": 6, "x": 0, "y": 0}),
        stat_panel(2, "Certification Records", "sum(tijara_hardware_certifications_total)", {"h": 4, "w": 6, "x": 6, "y": 0}),
        stat_panel(3, "Hardware Assumption Mode", 'max(tijara_external_assumption_mode{integration="hardware"})', {"h": 4, "w": 6, "x": 12, "y": 0}, "bool"),
        stat_panel(4, "Hardware Bridge Probe", 'max(probe_success{job="tijara-http-blackbox",instance=~".*hardware_bridge.*"})', {"h": 4, "w": 6, "x": 18, "y": 0}, "bool"),
        timeseries_panel(5, "Devices By Type And Status", [('sum by (device_type, integration_status) (tijara_hardware_devices_total)', "{{device_type}} / {{integration_status}}")], {"h": 8, "w": 12, "x": 0, "y": 4}),
        timeseries_panel(6, "Certification Results", [('sum by (device_type, result) (tijara_hardware_certifications_total)', "{{device_type}} / {{result}}")], {"h": 8, "w": 12, "x": 12, "y": 4}),
        timeseries_panel(7, "Endpoint Latency", [('probe_duration_seconds{job="tijara-http-blackbox"}', "{{instance}}")], {"h": 8, "w": 12, "x": 0, "y": 12}, "s"),
        bar_panel(8, "All External Certification Assumptions", "max by (integration) (tijara_external_assumption_mode)", "{{integration}}", {"h": 8, "w": 12, "x": 12, "y": 12}),
    ]
    return dashboard(
        "tijara-hardware-integrations",
        "Tijara Hardware And Integration Risk",
        ["tijara", "hardware", "integrations", "certification"],
        panels,
        "Hardware certification, bridge availability, device state, endpoint latency, and external integration assumption risks.",
    )


def dashboards() -> dict[str, dict]:
    return {
        "tijara-owner-devops-overview.json": owner_ops_dashboard(),
        "tijara-ecommerce-delivery-operations.json": delivery_dashboard(),
        "tijara-finance-psp-fbr-compliance.json": finance_dashboard(),
        "tijara-hardware-integration-risk.json": hardware_dashboard(),
    }


def normalized_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_dashboards(check: bool = False) -> int:
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    for filename, payload in dashboards().items():
        path = DASHBOARD_DIR / filename
        content = normalized_json(payload)
        if check:
            if not path.is_file():
                failures.append("%s missing" % path)
                continue
            current = path.read_text(encoding="utf-8")
            if current != content:
                failures.append("%s is not up to date" % path)
            continue
        path.write_text(content, encoding="utf-8")
        print("wrote %s" % path)
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    if check:
        print("Grafana dashboards are up to date.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Tijara Grafana dashboard JSON files.")
    parser.add_argument("--check", action="store_true", help="Verify committed dashboard JSON matches the generator.")
    args = parser.parse_args()
    return write_dashboards(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
