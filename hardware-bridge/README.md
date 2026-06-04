# Tijara Hardware Bridge

The Tijara Hardware Bridge is the local shop-machine service for printers,
cash drawers, scales, scanners, and customer displays. It is intentionally
open-source-first and dependency-light. The bridge uses Python's standard
library, writes auditable jobs to disk, and supports dry-run mode by default.

## Endpoints

- `GET /health`
- `POST /v1/test`
- `POST /v1/print/receipt`
- `POST /v1/print/label`
- `POST /v1/cash-drawer/open`
- `POST /v1/display/customer`
- `POST /v1/scale/read`
- `POST /v1/scan/event`

All POST requests require:

- `X-Tijara-Timestamp`: Unix timestamp.
- `X-Tijara-Signature`: `sha256=<hmac>`.

The signature is:

```text
HMAC-SHA256(TIJARA_BRIDGE_SHARED_SECRET, "<timestamp>.<raw-json-body>")
```

## Local Run

```bash
export TIJARA_BRIDGE_SHARED_SECRET=replace-with-dev-secret
export TIJARA_BRIDGE_DEVICE_CONFIG=hardware-bridge/config/devices.example.json
export TIJARA_BRIDGE_JOB_DIR=/tmp/tijara-bridge-jobs
export TIJARA_BRIDGE_OUTPUT_DIR=/tmp/tijara-bridge-output
PYTHONPATH=hardware-bridge python -m tijara_bridge.server
```

From the repository root, Docker Compose can run the bridge with the `hardware`
profile:

```bash
docker compose --profile hardware up -d hardware_bridge
```

## Driver Adapters

Dry-run mode records signed jobs and includes generated driver output metadata.
When `TIJARA_BRIDGE_DRY_RUN=False`, delivery can use:

- CUPS with `cups_printer`, `printer_name`, or `queue`.
- Raw TCP with `tcp_host`/`tcp_port`, `host`/`port`, or `ip_address`/`port`.
- File output with `output_file` or `TIJARA_BRIDGE_OUTPUT_DIR`.

Current adapter foundations:

- ESC/POS receipt bytes.
- ZPL label bytes.
- ESC/POS cash-drawer pulse bytes.
- Customer-display JSON state output.
- Scanner-event JSON persistence.
- Dry-run or TCP scale readings.

These adapter paths are production-shaped, but every physical printer, cash
drawer, display, and scale model must be certified with target hardware before
customer rollout.

## Odoo POS Receipt Flow

To route browser POS receipts through the bridge:

1. Configure `TIJARA_BRIDGE_SHARED_SECRET` for Odoo and the bridge.
2. Create a Tijara hardware device with:
   - `device_type`: `receipt_printer`
   - `connection_type`: `browser_bridge`
   - `printer_language`: `escpos`, `zpl`, or `cups` as appropriate
   - `bridge_endpoint`: the local bridge URL
3. Run `Bridge Health` and `Send Bridge Test Job` from Odoo.
4. Assign the hardware device as the Tijara receipt printer on the POS
   configuration.
5. Use the POS receipt print action after checkout. Odoo signs the bridge job
   and stores the print status, job id, response JSON, and printed timestamp on
   the POS order.
