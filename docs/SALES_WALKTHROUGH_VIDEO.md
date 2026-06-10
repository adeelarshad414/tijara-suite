# Sales Walkthrough Video Guide

This guide explains how the sales and training team should use the Tijara Suite
customer walkthrough video.

## Generated Assets

- Video: `docs/PRODUCT_DEMO_CUSTOMER.webm`
- Voiceover: `docs/video-clips/customer-demo/customer-demo-voiceover.wav`
- Recording spec: `docs/video-clips/customer-demo/customer-demo-recording-spec.json`
- Source script: `docs/VIDEO_SCRIPT.md`
- Generator: `scripts/generate_customer_demo_video.py`

The generated media files are ignored by git. Regenerate them locally whenever
the script, screenshots, or sales story changes.

## Generate The Video

On macOS with Chrome, `say`, `afconvert`, `ffmpeg`, and project dependencies:

```bash
make customer-demo-video
```

Direct command:

```bash
python3 scripts/generate_customer_demo_video.py
```

Optional environment values:

```bash
TIJARA_CUSTOMER_DEMO_WIDTH=1280 TIJARA_CUSTOMER_DEMO_HEIGHT=720 make customer-demo-video
TIJARA_CUSTOMER_DEMO_VOICE=Daniel make customer-demo-video
TIJARA_CUSTOMER_DEMO_ENCODER=browser make customer-demo-video
TIJARA_CUSTOMER_DEMO_BUILD_AVI=1 make customer-demo-video
```

The default encoder is `auto`, which uses `ffmpeg` when available and falls
back to the browser recorder only when needed. Prefer the default for sales
handoff videos because it avoids browser audio-capture stalls.

## How Sales Should Present It

Use the video as a two-part demo opener:

1. Play the generated WebM to explain the full product in a controlled story.
2. Open the live demo tenant and walk through only the workflows that match the
   customer's business vertical.

Recommended vertical-first follow-ups:

- Superstore or grocery: POS, B2B/B2C prices, inventory alerts, delivery, owner
  analytics.
- Pharmacy: expiry alerts, product batches, invoice printing, GST policy,
  customer records.
- Restaurant, cafe, fast food, bakery: kiosk, dine-in, takeaway, pickup, queue,
  menu, deals, service charges, delivery charges.
- Cloth, garments, uniform, shoes: product attributes, sizes, pricing,
  promotions, loyalty, inventory placement.
- Mobile, electronics, appliances: serial/warranty foundations, customer
  records, sales history, exchange/refund flow.
- Wholesale or multi-branch: B2B pricing, procurement, branch reporting,
  tenant/SaaS controls.

## Core Talking Points

- Pakistan-ready: PKR, GST policies, Urdu/English printing, FBR readiness,
  local PSP readiness, and local courier readiness.
- Counter-ready: touch, keyboard, scanner, barcode, QR, receipt printer,
  customer display, refund, exchange, and offline replay foundations.
- Manager-ready: expenses, salaries, purchases, suppliers, customers, loyalty,
  promotions, analytics, charts, reports, and history.
- SaaS-ready: feature flags for B2B, kiosk, queue, customer display, promotion
  display, ecommerce, delivery operations, analytics, and hardware bridge.
- DevOps-ready: central config, central secrets, Bash/PowerShell/Python
  scripts, monitoring dashboards, backup/restore docs, release gates, and
  protected evidence chain.

## Important Sales Guardrails

Do not sell dummy integrations as live certified integrations.

Use this wording:

- "The foundation and demo flow are built."
- "The adapter and evidence paths exist."
- "Production go-live requires certified credentials, real hardware testing,
  provider sign-off, and protected staging evidence."

Certification areas that still need real customer or provider work:

- FBR certified provider API and credentials.
- JazzCash, Easypaisa, Stripe, and PSP refund/chargeback/reconciliation
  certification.
- Courier provider live API and webhook certification.
- Printers, cash drawers, barcode scanners, scales, labels, and customer
  displays on physical devices.
- DNS, TLS, ingress, monitoring, backups, restore drills, load tests, and
  security scans on protected staging/production infrastructure.

## Suggested Call Flow

1. Confirm the customer's vertical and branch count.
2. Play the customer walkthrough video.
3. Ask which three workflows matter most this month.
4. Show the matching live screens or screenshots.
5. Review the production readiness checklist.
6. Propose a pilot scope with users, devices, integrations, and reporting.

## Related Documents

- `ABOUT.md`
- `README.md`
- `DEPLOY.md`
- `docs/VIDEO_SCRIPT.md`
- `docs/USER_GUIDE_ALL_USERS.md`
- `docs/VISUAL_USER_GUIDE_ALL_FUNCTIONS.md`
- `docs/SCREENSHOT_USER_GUIDE.md`
- `docs/TEST_CREDENTIALS.csv`
- `docs/PRODUCTION_READINESS_CHECKLIST.md`
