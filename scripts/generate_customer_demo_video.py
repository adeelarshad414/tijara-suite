#!/usr/bin/env python3
import html
import math
import os
import shutil
import struct
import subprocess
import json
import wave
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
WORK_DIR = ROOT_DIR / "docs/video-clips/customer-demo"
OUTPUT_WEBM = ROOT_DIR / "docs/PRODUCT_DEMO_CUSTOMER.webm"
OUTPUT_AVI = WORK_DIR / "customer-demo-narrated.avi"
OUTPUT_WAV = WORK_DIR / "customer-demo-voiceover.wav"
WIDTH = int(os.environ.get("TIJARA_CUSTOMER_DEMO_WIDTH", "960"))
HEIGHT = int(os.environ.get("TIJARA_CUSTOMER_DEMO_HEIGHT", "540"))
FPS = int(os.environ.get("TIJARA_CUSTOMER_DEMO_FPS", "2"))
SAMPLE_RATE = int(os.environ.get("TIJARA_CUSTOMER_DEMO_SAMPLE_RATE", "22050"))
VOICE = os.environ.get("TIJARA_CUSTOMER_DEMO_VOICE", "")
CHROME = Path(os.environ.get("TIJARA_CUSTOMER_DEMO_CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
ENCODER = os.environ.get("TIJARA_CUSTOMER_DEMO_ENCODER", "auto").strip().lower()


SCENES = [
    {
        "slug": "intro",
        "eyebrow": "Customer sales walkthrough",
        "title": "Tijara Suite for Pakistani businesses",
        "subtitle": "A modular Odoo Community suite for POS, inventory, restaurant, ecommerce, back office, analytics, SaaS control, and hardware readiness.",
        "bullets": [
            "Built for superstores, groceries, pharmacies, restaurants, bakeries, garments, shoes, mobile, electronics, and wholesale.",
            "PKR, GST policy, Urdu/English printing, barcode workflows, customer display, queue, kiosk, and delivery readiness.",
            "Open-source-first foundation that can start locally and mature into hosted SaaS.",
        ],
        "metric": "Enterprise retail and restaurant platform",
        "screenshot": "docs/screenshots/platform-superadmin/odoo-login.png",
        "screen_label": "Login and onboarding",
        "screen_notes": ["Public-safe demo", "Role-based access", "SaaS-ready", "Pakistan-first"],
        "voiceover": (
            "Welcome to Tijara Suite, a Pakistan-focused business platform built on Odoo Community. "
            "This customer walkthrough shows how one suite can cover point of sale, inventory, restaurant service, ecommerce, back office, analytics, SaaS controls, and hardware readiness for real Pakistani businesses."
        ),
    },
    {
        "slug": "personas",
        "eyebrow": "Persona-led training",
        "title": "One system for every role",
        "subtitle": "Sales teams can explain the product through the people who use it every day.",
        "bullets": [
            "Owner, tenant admin, cashier, inventory manager, accountant, restaurant operator, ecommerce manager, and DevOps.",
            "Each persona has seeded workflows and public-safe demo credentials.",
            "Dashboards, screens, and guides are organized for onboarding and training.",
        ],
        "metric": "15 demo personas",
        "screenshot": "docs/screenshots/tenant-admin/odoo-app-shell.png",
        "screen_label": "Role-based app shell",
        "screen_notes": ["Owner", "Cashier", "Back office", "DevOps"],
        "voiceover": (
            "The easiest way to sell and train Tijara is by persona. "
            "Owners look at trends and margins, cashiers run fast checkout, inventory teams control stock, accountants review payments and taxes, restaurant teams manage queues, and DevOps teams run the release and monitoring process."
        ),
    },
    {
        "slug": "pos-cashier",
        "eyebrow": "Cashier and counter workflow",
        "title": "POS for B2C, B2B, refunds, and printing",
        "subtitle": "The counter flow is designed for touch, barcode scanners, keyboard use, and Enter-friendly cashier operation.",
        "bullets": [
            "B2C and B2B prices are handled separately on inventory products.",
            "Bill discount supports amount or percentage with automatic calculation sync.",
            "Refund and exchange flow can start from invoice barcode scanning.",
        ],
        "metric": "Checkout, refund, print, replay",
        "screenshot": "docs/screenshots/cashier/customer-display.png",
        "screen_label": "POS and customer display",
        "screen_notes": ["B2B/B2C", "Barcode", "Discount", "Receipt"],
        "voiceover": (
            "At the counter, cashiers can sell to walk-in retail customers or wholesale B2B customers, scan products, use keyboard shortcuts, apply a discount by amount or percentage, print receipts, and process refunds or exchanges by scanning the invoice barcode."
        ),
    },
    {
        "slug": "restaurant-kiosk",
        "eyebrow": "Restaurant, cafe, and bakery",
        "title": "Dine-in, takeaway, pickup, and kiosk",
        "subtitle": "Food-service businesses get self-ordering, menu boards, queue screens, deals displays, and service-mode policies.",
        "bullets": [
            "Restaurant mode supports dine-in, takeaway, pickup, and delivery.",
            "Cafe and restaurant policies can enable GST, card/cash tax rates, service charges, and delivery charges.",
            "Kiosk, queue, menu, deals, and promotion screens are SaaS-controlled features.",
        ],
        "metric": "Kiosk and queue-ready",
        "screenshot": "docs/screenshots/public-display/kiosk-display.png",
        "screen_label": "Kiosk ordering",
        "screen_notes": ["Dine-in", "Takeaway", "Pickup", "Deals"],
        "voiceover": (
            "For restaurants, cafes, fast food, and bakeries, Tijara supports dine-in, takeaway, pickup, and delivery. "
            "Customers can use a kiosk, managers can publish menu and deal screens, and the business can control GST, card and cash tax rules, service charges, and delivery charges."
        ),
    },
    {
        "slug": "queue-displays",
        "eyebrow": "Screen features",
        "title": "Queue, customer, menu, deal, and promotion displays",
        "subtitle": "Customer-facing screens help stores guide the buyer and reduce counter confusion.",
        "bullets": [
            "Queue screens show waiting, preparing, ready, and called order states.",
            "Customer display shows cart lines, totals, receipt context, and checkout status.",
            "Menu, deal, and promotion screens can be switched on per tenant plan.",
        ],
        "metric": "Display features as SaaS add-ons",
        "screenshot": "docs/screenshots/restaurant-operator/queue-display.png",
        "screen_label": "Queue display",
        "screen_notes": ["Waiting", "Preparing", "Ready", "Called"],
        "voiceover": (
            "Tijara also gives businesses customer-facing screens. "
            "A queue display keeps restaurant and pickup flow clear, a customer display shows cart and total information, and promotion, menu, and deal boards help sell more from the same counter."
        ),
    },
    {
        "slug": "inventory-verticals",
        "eyebrow": "Inventory and vertical control",
        "title": "Stock, expiry, racks, shelves, and business policies",
        "subtitle": "Inventory and policy controls adapt to superstore, grocery, pharmacy, cloth, garments, shoes, mobile, electronics, and food businesses.",
        "bullets": [
            "Track stock by warehouse, store, rack, shelf, bin, aisle, and placement.",
            "Use low-stock and expiry alerts for pharmacy, grocery, bakery, and perishable items.",
            "Enable or disable GST, service charges, delivery charges, and vertical-specific policies.",
        ],
        "metric": "Inventory plus policy intelligence",
        "screenshot": "docs/screenshots/tenant-admin/business-policy-settings.png",
        "screen_label": "Business policy settings",
        "screen_notes": ["GST", "Service charge", "Delivery", "Verticals"],
        "voiceover": (
            "Inventory managers can control products, prices, stock, expiry, and locations such as warehouse, rack, shelf, bin, and aisle. "
            "Tenant admins can also manage business policies for GST, service charges, delivery fees, cafe rules, restaurant rules, and vertical-specific workflows."
        ),
    },
    {
        "slug": "back-office-expenses",
        "eyebrow": "Back-office operations",
        "title": "Expenses, purchases, procurement, and salaries",
        "subtitle": "The back office gives owners and managers daily control beyond the cash counter.",
        "bullets": [
            "Expense and salary records support operational review and owner reporting.",
            "Purchase, procurement, supplier, customer, and import/export workflows are part of the suite plan.",
            "Each record is built for history, audit, dashboards, and manager approval patterns.",
        ],
        "metric": "Owner and manager control",
        "screenshot": "docs/screenshots/accountant/expense-management.png",
        "screen_label": "Expense management",
        "screen_notes": ["Expenses", "Purchases", "Suppliers", "Audit"],
        "voiceover": (
            "Back-office users can manage expenses, salaries, purchases, procurement, suppliers, and customer records. "
            "The goal is to give owners a practical operating system where every record can feed reports, approvals, and audit history."
        ),
    },
    {
        "slug": "salary-operations",
        "eyebrow": "People and branch operations",
        "title": "Salary records and operating history",
        "subtitle": "Managers can track staff-related cost records as part of the same business suite.",
        "bullets": [
            "Salary records are included for back-office and owner visibility.",
            "Operations can be reviewed by role, branch, business vertical, and reporting period.",
            "The same role matrix supports training, access control, and staged customer demos.",
        ],
        "metric": "People cost visibility",
        "screenshot": "docs/screenshots/salary-manager/salary-management.png",
        "screen_label": "Salary management",
        "screen_notes": ["Staff", "Cost", "History", "Reports"],
        "voiceover": (
            "For growing businesses, operating cost matters. "
            "Tijara includes salary management foundations so staff-related costs can sit beside expenses, sales, purchase, inventory, and branch performance in one operating view."
        ),
    },
    {
        "slug": "ecommerce-delivery",
        "eyebrow": "Online selling and delivery",
        "title": "Ecommerce, customer portal, and delivery operations",
        "subtitle": "Online orders connect to customer records, delivery providers, reconciliation, and return or exchange requests.",
        "bullets": [
            "Storefront, checkout, account portal, saved addresses, and order history are included.",
            "Pakistan courier and in-house rider adapters have dummy-safe provider fixtures.",
            "Delivery retry queue, SLA exceptions, and reconciliation reports support operations.",
        ],
        "metric": "Online plus store operations",
        "screenshot": "docs/screenshots/public-display/ecommerce-storefront.png",
        "screen_label": "Ecommerce storefront",
        "screen_notes": ["Checkout", "Portal", "Delivery", "Returns"],
        "voiceover": (
            "Tijara is not only a counter system. "
            "It includes ecommerce storefront and customer account foundations, saved addresses, order history, return requests, Pakistan courier profiles, in-house rider support, delivery retries, SLA exceptions, and delivery reconciliation."
        ),
    },
    {
        "slug": "loyalty-promotions",
        "eyebrow": "Customer growth tools",
        "title": "Customers, loyalty, promotions, menus, and deals",
        "subtitle": "Sales teams can show how the suite helps businesses retain buyers and run campaigns.",
        "bullets": [
            "Customer records support walk-in conversion, loyalty, order history, and returns.",
            "Promotions and deals can target retail, restaurant, bakery, grocery, and branch campaigns.",
            "Promotion display and customer display are controllable SaaS add-ons.",
        ],
        "metric": "Retention and campaigns",
        "screenshot": "docs/screenshots/loyalty-manager/loyalty-customer-records.png",
        "screen_label": "Loyalty customer records",
        "screen_notes": ["Customers", "Loyalty", "Deals", "Campaigns"],
        "voiceover": (
            "For growth, Tijara connects customer records, loyalty foundations, promotions, deals, menus, and display screens. "
            "A business can start simple with walk-in sales, then add loyalty, campaigns, and display upsell features as the plan grows."
        ),
    },
    {
        "slug": "analytics",
        "eyebrow": "Owner dashboard and analytics",
        "title": "Trends, charts, reports, and KPI history",
        "subtitle": "Owners and managers get the reports needed to run the business, not just close sales.",
        "bullets": [
            "Dashboards cover sales, inventory, expenses, salaries, loyalty, vertical performance, delivery, PSP, FBR, and hardware state.",
            "KPI collectors create trend, history, report, and alert evidence for managers.",
            "Grafana and Odoo dashboards support business and DevOps visibility.",
        ],
        "metric": "Decision-ready analytics",
        "screenshot_options": [
            "deploy/runtime/grafana-dashboard-evidence/*/screenshots/tijara-owner-ops.png",
            "docs/screenshots/tenant-admin/analytics-dashboards.png",
        ],
        "screen_label": "Analytics dashboard",
        "screen_notes": ["Trends", "Charts", "KPIs", "Reports"],
        "voiceover": (
            "Owners need more than bills. "
            "Tijara tracks trends, history, charts, reports, and dashboards for sales, inventory, expenses, salary liability, loyalty, verticals, delivery, payments, FBR queues, hardware readiness, and DevOps operations."
        ),
    },
    {
        "slug": "enterprise-readiness",
        "eyebrow": "Enterprise delivery and honest readiness",
        "title": "SaaS controls, security, DevOps, FBR, PSP, and hardware",
        "subtitle": "The product includes enterprise scaffolding while clearly separating demo assumptions from certified production evidence.",
        "bullets": [
            "Feature flags, tenant provisioning, monitoring, backups, release gates, and protected evidence are documented.",
            "Hardware bridge covers printers, scanners, drawers, scales, labels, and customer displays in dummy-safe mode.",
            "FBR, JazzCash, Easypaisa, Stripe, courier, and device integrations still need real certification before go-live.",
        ],
        "metric": "Pilot-ready, certification-aware",
        "screenshot_options": [
            "deploy/runtime/grafana-dashboard-evidence/*/screenshots/tijara-finance-fbr.png",
            "deploy/runtime/grafana-dashboard-evidence/*/screenshots/tijara-hardware-integrations.png",
            "docs/screenshots/platform-superadmin/payment-webhook.png",
        ],
        "screen_label": "Payment and integration readiness",
        "screen_notes": ["SaaS", "FBR", "PSP", "Hardware"],
        "voiceover": (
            "For enterprise delivery, Tijara includes SaaS feature flags, tenant provisioning foundations, monitoring dashboards, backups, release gates, protected evidence, hardware bridge readiness, FBR queue readiness, and PSP adapter readiness. "
            "For production go-live, real devices, provider credentials, and certified compliance evidence are still required."
        ),
    },
    {
        "slug": "closing",
        "eyebrow": "Sales close",
        "title": "Modular rollout for every business size",
        "subtitle": "Start with the right vertical, enable features by plan, train each role, and grow toward production-certified SaaS.",
        "bullets": [
            "Best pilot paths: retail POS, restaurant kiosk and queue, inventory alerts, ecommerce, and owner dashboards.",
            "Best sales message: one open-source-first suite, many business verticals, SaaS-controlled features.",
            "Best next step: run a demo tenant with seeded users and choose the first customer vertical.",
        ],
        "metric": "Ready for customer demos",
        "screenshot": "docs/screenshots/promotion-manager/promotions-management.png",
        "screen_label": "Promotions management",
        "screen_notes": ["Pilot", "Train", "Launch", "Scale"],
        "voiceover": (
            "Tijara Suite gives the sales team a clear customer story. "
            "Start with one vertical, demonstrate the key persona workflows, enable the right SaaS features, and move from pilot to production only after the needed hardware, payment, FBR, courier, security, and infrastructure evidence is complete."
        ),
    },
]


def _run(command):
    subprocess.run(command, check=True)


def _build_avi_enabled():
    return os.environ.get("TIJARA_CUSTOMER_DEMO_BUILD_AVI", "").strip().lower() in {"1", "true", "yes", "on"}


def _require_tools(build_avi):
    missing = []
    for tool in ["say", "afconvert"]:
        if not shutil.which(tool):
            missing.append(tool)
    if ENCODER == "browser" and not shutil.which("node"):
        missing.append("node")
    if ENCODER == "ffmpeg" and not shutil.which("ffmpeg"):
        missing.append("ffmpeg")
    if ENCODER == "auto" and not shutil.which("ffmpeg") and not shutil.which("node"):
        missing.append("ffmpeg or node")
    if build_avi and not shutil.which("sips"):
        missing.append("sips")
    if not CHROME.is_file():
        missing.append(str(CHROME))
    if missing:
        raise SystemExit("Missing required tool(s): %s" % ", ".join(missing))


def _chunk(fourcc, data):
    payload = fourcc + struct.pack("<I", len(data)) + data
    if len(data) % 2:
        payload += b"\0"
    return payload


def _list(kind, data):
    return b"LIST" + struct.pack("<I", len(data) + 4) + kind + data


def _resolve_screenshot_path(scene):
    candidates = list(scene.get("screenshot_options") or [])
    if scene.get("screenshot"):
        candidates.append(scene["screenshot"])
    for candidate in candidates:
        if any(marker in candidate for marker in "*?[]"):
            paths = sorted(ROOT_DIR.glob(candidate), reverse=True)
        else:
            paths = [ROOT_DIR / candidate]
        for path in paths:
            if path.is_file():
                return path.resolve()
    return None


def _scene_html(scene, index):
    bullets = "\n".join("<li>%s</li>" % html.escape(item) for item in scene["bullets"])
    accent = ["#1f7a8c", "#0f766e", "#b45309", "#2563eb", "#7c3aed", "#be123c", "#334155", "#047857"][index % 8]
    screen_notes = scene.get("screen_notes") or []
    note_rows = "\n".join('<div class="note">%s</div>' % html.escape(item) for item in screen_notes[:4])
    screenshot_markup = ""
    screenshot_path = _resolve_screenshot_path(scene)
    if screenshot_path:
        screenshot_markup = (
            '<div class="screenshot-frame">'
            '<img src="%s" alt="%s">'
            "</div>"
        ) % (
            html.escape(screenshot_path.as_uri()),
            html.escape(scene.get("screen_label") or scene["title"]),
        )
    if not screenshot_markup:
        screenshot_markup = '<div class="screenshot-missing">Feature overview screen</div>'
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    width: {WIDTH}px;
    height: {HEIGHT}px;
    overflow: hidden;
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #f7f8fb;
    color: #172033;
  }}
  .stage {{
    width: {WIDTH}px;
    height: {HEIGHT}px;
    padding: 32px;
    display: grid;
    grid-template-columns: 1.02fr .98fr;
    gap: 28px;
    background:
      linear-gradient(120deg, rgba(255,255,255,.94), rgba(247,248,251,.92)),
      radial-gradient(circle at 18% 12%, rgba(31,122,140,.16), transparent 34%),
      radial-gradient(circle at 90% 90%, rgba(180,83,9,.13), transparent 35%);
  }}
  .brand {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 0;
    margin-bottom: 28px;
  }}
  .mark {{
    width: 34px;
    height: 34px;
    border-radius: 7px;
    background: {accent};
    color: white;
    display: grid;
    place-items: center;
    font-weight: 900;
  }}
  .eyebrow {{
    color: {accent};
    font-size: 15px;
    font-weight: 800;
    margin-bottom: 8px;
  }}
  h1 {{
    font-size: 38px;
    line-height: 1.05;
    margin: 0 0 12px;
    letter-spacing: 0;
  }}
  .subtitle {{
    font-size: 17px;
    line-height: 1.36;
    color: #4b5563;
    margin-bottom: 18px;
  }}
  ul {{
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 8px;
  }}
  li {{
    font-size: 15px;
    line-height: 1.32;
    padding-left: 28px;
    position: relative;
  }}
  li:before {{
    content: "";
    position: absolute;
    left: 0;
    top: 8px;
    width: 10px;
    height: 10px;
    border-radius: 3px;
    background: {accent};
  }}
  .panel {{
    background: white;
    border: 1px solid #e3e7ee;
    border-radius: 8px;
    box-shadow: 0 18px 45px rgba(15,23,42,.12);
    overflow: hidden;
    align-self: stretch;
    display: grid;
    grid-template-rows: 52px 1fr;
  }}
  .topbar {{
    background: #111827;
    color: #f9fafb;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 18px;
    font-size: 14px;
  }}
  .dots span {{
    display: inline-block;
    width: 10px;
    height: 10px;
    margin-right: 6px;
    border-radius: 10px;
    background: #ef4444;
  }}
  .dots span:nth-child(2) {{ background: #f59e0b; }}
  .dots span:nth-child(3) {{ background: #22c55e; }}
  .screen {{
    padding: 16px;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr) auto;
    gap: 12px;
    background: #fbfcfe;
    min-height: 0;
  }}
  .metric {{
    border-left: 5px solid {accent};
    background: #fff;
    border-radius: 8px;
    padding: 13px 14px;
    font-size: 21px;
    font-weight: 850;
  }}
  .screenshot-frame {{
    min-height: 0;
    border: 1px solid #dce3ec;
    border-radius: 8px;
    background: #e5e7eb;
    overflow: hidden;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.42);
  }}
  .screenshot-frame img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: top left;
    display: block;
  }}
  .screenshot-missing {{
    border: 1px dashed #cbd5e1;
    border-radius: 8px;
    display: grid;
    place-items: center;
    min-height: 230px;
    color: #64748b;
    font-weight: 800;
    background: #fff;
  }}
  .screen-notes {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }}
  .note {{
    min-height: 34px;
    display: grid;
    place-items: center;
    border: 1px solid #e5e7eb;
    border-radius: 7px;
    background: #fff;
    color: #334155;
    font-size: 13px;
    font-weight: 800;
    text-align: center;
  }}
  .footer {{
    position: absolute;
    left: 32px;
    bottom: 22px;
    font-size: 13px;
    color: #64748b;
  }}
</style>
</head>
<body>
  <div class="stage">
    <section>
      <div class="brand"><div class="mark">T</div><div>Tijara Suite</div></div>
      <div class="eyebrow">{html.escape(scene["eyebrow"])}</div>
      <h1>{html.escape(scene["title"])}</h1>
      <div class="subtitle">{html.escape(scene["subtitle"])}</div>
      <ul>{bullets}</ul>
      <div class="footer">Customer demo with generated voiceover</div>
    </section>
    <section class="panel">
      <div class="topbar"><div class="dots"><span></span><span></span><span></span></div><div>{html.escape(scene.get("screen_label") or scene["slug"]).replace("-", " ").title()}</div></div>
      <div class="screen">
        <div class="metric">{html.escape(scene["metric"])}</div>
        {screenshot_markup}
        <div class="screen-notes">{note_rows}</div>
      </div>
    </section>
  </div>
</body>
</html>"""


def _render_scene(scene, index, build_avi):
    html_path = WORK_DIR / ("%02d-%s.html" % (index + 1, scene["slug"]))
    png_path = WORK_DIR / ("%02d-%s.png" % (index + 1, scene["slug"]))
    bmp_path = WORK_DIR / ("%02d-%s.bmp" % (index + 1, scene["slug"]))
    html_path.write_text(_scene_html(scene, index), encoding="utf-8")
    _run(
        [
            str(CHROME),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--window-size=%s,%s" % (WIDTH, HEIGHT),
            "--screenshot=%s" % png_path,
            html_path.resolve().as_uri(),
        ]
    )
    if not build_avi:
        return None
    _run(["sips", "-s", "format", "bmp", str(png_path), "--out", str(bmp_path)])
    return _read_bmp_as_dib(bmp_path)


def _read_bmp_as_dib(path):
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError("Not a BMP file: %s" % path)
    off_bits = struct.unpack_from("<I", data, 10)[0]
    header_size = struct.unpack_from("<I", data, 14)[0]
    width = struct.unpack_from("<i", data, 18)[0]
    height_raw = struct.unpack_from("<i", data, 22)[0]
    bit_count = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]
    if header_size < 40 or width != WIDTH or abs(height_raw) != HEIGHT or compression != 0:
        raise ValueError("Unsupported BMP geometry or compression: %s" % path)
    top_down = height_raw < 0
    source_height = abs(height_raw)
    if bit_count not in (24, 32):
        raise ValueError("Unsupported BMP bit depth %s: %s" % (bit_count, path))
    source_stride = ((width * bit_count + 31) // 32) * 4
    target_stride = ((width * 3 + 3) // 4) * 4
    rows = []
    for y in range(source_height):
        source_y = y if top_down else source_height - 1 - y
        start = off_bits + source_y * source_stride
        row = bytearray()
        for x in range(width):
            pixel = data[start + x * (bit_count // 8) : start + x * (bit_count // 8) + 3]
            row.extend(pixel)
        row.extend(b"\0" * (target_stride - len(row)))
        rows.append(bytes(row))
    return b"".join(rows)


def _synthesize_scene(scene, index):
    aiff_path = WORK_DIR / ("%02d-%s.aiff" % (index + 1, scene["slug"]))
    wav_path = WORK_DIR / ("%02d-%s.wav" % (index + 1, scene["slug"]))
    say_command = ["say"]
    if VOICE:
        say_command.extend(["-v", VOICE])
    say_command.extend(["-o", str(aiff_path), scene["voiceover"]])
    _run(say_command)
    _run(["afconvert", "-f", "WAVE", "-d", "LEI16@%s" % SAMPLE_RATE, "-c", "1", str(aiff_path), str(wav_path)])
    with wave.open(str(wav_path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if channels != 1 or sample_width != 2 or sample_rate != SAMPLE_RATE:
        raise ValueError("Unexpected WAV format for %s" % wav_path)
    silence = b"\0" * int(SAMPLE_RATE * 0.45) * 2
    return frames + silence


def _avi_header(total_frames, total_audio_samples, image_size):
    microseconds_per_frame = int(1_000_000 / FPS)
    block_align = 2
    byte_rate = SAMPLE_RATE * block_align
    avih = struct.pack(
        "<IIIIIIIIII4I",
        microseconds_per_frame,
        image_size * FPS + byte_rate,
        0,
        0x10,
        total_frames,
        0,
        2,
        image_size,
        WIDTH,
        HEIGHT,
        0,
        0,
        0,
        0,
    )
    video_strh = struct.pack(
        "<4s4sIHHIIIIIIIIhhhh",
        b"vids",
        b"DIB ",
        0,
        0,
        0,
        0,
        1,
        FPS,
        0,
        total_frames,
        image_size,
        0xFFFFFFFF,
        0,
        0,
        0,
        WIDTH,
        HEIGHT,
    )
    video_strf = struct.pack(
        "<IiiHHIIiiII",
        40,
        WIDTH,
        HEIGHT,
        1,
        24,
        0,
        image_size,
        0,
        0,
        0,
        0,
    )
    audio_strh = struct.pack(
        "<4s4sIHHIIIIIIIIhhhh",
        b"auds",
        b"\0\0\0\0",
        0,
        0,
        0,
        0,
        block_align,
        byte_rate,
        0,
        total_audio_samples,
        int(SAMPLE_RATE / FPS) * block_align,
        0xFFFFFFFF,
        block_align,
        0,
        0,
        0,
        0,
    )
    audio_strf = struct.pack("<HHIIHH", 1, 1, SAMPLE_RATE, byte_rate, block_align, 16)
    video_strl = _list(b"strl", _chunk(b"strh", video_strh) + _chunk(b"strf", video_strf))
    audio_strl = _list(b"strl", _chunk(b"strh", audio_strh) + _chunk(b"strf", audio_strf))
    return _list(b"hdrl", _chunk(b"avih", avih) + video_strl + audio_strl)


def _write_avi(slides, scene_audio):
    frame_samples = int(SAMPLE_RATE / FPS)
    image_size = len(slides[0])
    video_frames = []
    audio = bytearray()
    for index, audio_bytes in enumerate(scene_audio):
        scene_samples = len(audio_bytes) // 2
        frames = max(1, math.ceil(scene_samples / frame_samples))
        video_frames.extend([slides[index]] * frames)
        padded = bytearray(audio_bytes)
        padded.extend(b"\0" * ((frames * frame_samples * 2) - len(padded)))
        audio.extend(padded)

    total_frames = len(video_frames)
    total_audio_samples = len(audio) // 2
    movi_data = bytearray()
    index_entries = []
    audio_offset = 0
    audio_frame_bytes = frame_samples * 2
    for frame in video_frames:
        offset = len(movi_data) + 4
        movi_data.extend(_chunk(b"00db", frame))
        index_entries.append((b"00db", 0x10, offset, len(frame)))
        chunk_audio = bytes(audio[audio_offset : audio_offset + audio_frame_bytes])
        audio_offset += audio_frame_bytes
        offset = len(movi_data) + 4
        movi_data.extend(_chunk(b"01wb", chunk_audio))
        index_entries.append((b"01wb", 0x10, offset, len(chunk_audio)))

    hdrl = _avi_header(total_frames, total_audio_samples, image_size)
    movi = _list(b"movi", bytes(movi_data))
    idx1 = b"".join(struct.pack("<4sIII", fourcc, flags, offset, size) for fourcc, flags, offset, size in index_entries)
    riff_payload = hdrl + movi + _chunk(b"idx1", idx1)
    OUTPUT_AVI.write_bytes(b"RIFF" + struct.pack("<I", len(riff_payload) + 4) + b"AVI " + riff_payload)
    return total_frames, total_audio_samples


def _write_combined_wav(scene_audio):
    combined = b"".join(scene_audio)
    with wave.open(str(OUTPUT_WAV), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(combined)
    return len(combined) // 2


def _record_webm_with_ffmpeg(scenes, scene_audio):
    if not shutil.which("ffmpeg"):
        raise FileNotFoundError("ffmpeg is not installed")
    concat_path = WORK_DIR / "customer-demo-ffmpeg-list.txt"
    spec_path = WORK_DIR / "customer-demo-recording-spec.json"
    lines = []
    scene_specs = []
    timeline = 0.0
    for index, scene in enumerate(scenes):
        duration = len(scene_audio[index]) / 2 / SAMPLE_RATE
        png_path = WORK_DIR / ("%02d-%s.png" % (index + 1, scene["slug"]))
        lines.append("file '%s'\n" % str(png_path).replace("'", "'\\''"))
        lines.append("duration %.3f\n" % duration)
        scene_specs.append(
            {
                "slug": scene["slug"],
                "title": scene["title"],
                "start": timeline,
                "end": timeline + duration,
                "png": str(png_path),
            }
        )
        timeline += duration
    last_png = WORK_DIR / ("%02d-%s.png" % (len(scenes), scenes[-1]["slug"]))
    lines.append("file '%s'\n" % str(last_png).replace("'", "'\\''"))
    concat_path.write_text("".join(lines), encoding="utf-8")
    spec_path.write_text(
        json.dumps(
            {
                "width": WIDTH,
                "height": HEIGHT,
                "fps": max(6, FPS * 4),
                "encoder": "ffmpeg",
                "audio": str(OUTPUT_WAV),
                "output": str(OUTPUT_WEBM),
                "duration": timeline,
                "scenes": scene_specs,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-i",
            str(OUTPUT_WAV),
            "-vf",
            "fps=%s,format=yuv420p" % max(6, FPS * 4),
            "-c:v",
            "libvpx-vp9",
            "-b:v",
            "2200k",
            "-c:a",
            "libopus",
            "-b:a",
            "128k",
            "-shortest",
            str(OUTPUT_WEBM),
        ]
    )
    return timeline


def _record_webm_with_browser(scenes, scene_audio):
    if not shutil.which("node"):
        raise FileNotFoundError("node is not installed")
    scene_specs = []
    timeline = 0.0
    for index, scene in enumerate(scenes):
        duration = len(scene_audio[index]) / 2 / SAMPLE_RATE
        png_path = WORK_DIR / ("%02d-%s.png" % (index + 1, scene["slug"]))
        scene_specs.append(
            {
                "slug": scene["slug"],
                "title": scene["title"],
                "start": timeline,
                "end": timeline + duration,
                "png": str(png_path),
            }
        )
        timeline += duration
    spec_path = WORK_DIR / "customer-demo-recording-spec.json"
    node_path = WORK_DIR / "record-customer-demo-webm.mjs"
    spec = {
        "width": WIDTH,
        "height": HEIGHT,
        "fps": max(6, FPS * 4),
        "chrome": str(CHROME),
        "audio": str(OUTPUT_WAV),
        "output": str(OUTPUT_WEBM),
        "duration": timeline,
        "scenes": scene_specs,
    }
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    node_path.write_text(
        r'''
import fs from "fs";
import { chromium } from "@playwright/test";

const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const imageData = spec.scenes.map((scene) => ({
  ...scene,
  dataUrl: "data:image/png;base64," + fs.readFileSync(scene.png).toString("base64"),
}));
const audioDataUrl = "data:audio/wav;base64," + fs.readFileSync(spec.audio).toString("base64");

const browser = await chromium.launch({
  headless: true,
  executablePath: spec.chrome,
  args: [
    "--autoplay-policy=no-user-gesture-required",
    "--disable-gpu",
    "--no-sandbox",
    "--use-fake-ui-for-media-stream",
  ],
});
const page = await browser.newPage({ viewport: { width: spec.width, height: spec.height } });
await page.setContent("<html><body style='margin:0;background:#111827'></body></html>");
const bytes = await page.evaluate(async ({ spec, imageData, audioDataUrl }) => {
  const canvas = document.createElement("canvas");
  canvas.width = spec.width;
  canvas.height = spec.height;
  document.body.appendChild(canvas);
  const context = canvas.getContext("2d");
  const images = await Promise.all(imageData.map((scene) => new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve({ ...scene, image });
    image.onerror = reject;
    image.src = scene.dataUrl;
  })));
  const audio = new Audio(audioDataUrl);
  audio.preload = "auto";
  await new Promise((resolve, reject) => {
    audio.oncanplaythrough = resolve;
    audio.onerror = reject;
    audio.load();
  });

  function activeScene() {
    const time = audio.currentTime || 0;
    return images.find((scene) => time >= scene.start && time < scene.end) || images[images.length - 1];
  }

  function draw() {
    const scene = activeScene();
    context.drawImage(scene.image, 0, 0, spec.width, spec.height);
    const progress = Math.min(1, (audio.currentTime || 0) / Math.max(spec.duration, 1));
    context.fillStyle = "rgba(15, 23, 42, 0.28)";
    context.fillRect(0, spec.height - 6, spec.width, 6);
    context.fillStyle = "rgba(31, 122, 140, 0.96)";
    context.fillRect(0, spec.height - 6, Math.round(spec.width * progress), 6);
    if (!audio.ended) requestAnimationFrame(draw);
  }

  const canvasStream = canvas.captureStream(spec.fps);
  const capture = audio.captureStream || audio.mozCaptureStream;
  if (!capture) throw new Error("Audio captureStream is not supported by this browser.");
  const audioStream = capture.call(audio);
  const mixed = new MediaStream([
    ...canvasStream.getVideoTracks(),
    ...audioStream.getAudioTracks(),
  ]);
  const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
    ? "video/webm;codecs=vp9,opus"
    : "video/webm;codecs=vp8,opus";
  const recorder = new MediaRecorder(mixed, {
    mimeType,
    videoBitsPerSecond: 2200000,
    audioBitsPerSecond: 128000,
  });
  const chunks = [];
  recorder.ondataavailable = (event) => {
    if (event.data && event.data.size) chunks.push(event.data);
  };
  const stopped = new Promise((resolve) => {
    recorder.onstop = resolve;
  });
  recorder.start(250);
  draw();
  await audio.play();
  await new Promise((resolve) => {
    audio.onended = () => {
      setTimeout(() => {
        recorder.stop();
        resolve();
      }, 350);
    };
  });
  await stopped;
  const blob = new Blob(chunks, { type: mimeType });
  const buffer = await blob.arrayBuffer();
  return Array.from(new Uint8Array(buffer));
}, { spec, imageData, audioDataUrl });
await browser.close();
fs.writeFileSync(spec.output, Buffer.from(bytes));
console.log(`webm=${spec.output}`);
console.log(`bytes=${bytes.length}`);
'''.strip()
        + "\n",
        encoding="utf-8",
    )
    _run(["node", str(node_path), str(spec_path)])
    return timeline


def main():
    build_avi = _build_avi_enabled()
    _require_tools(build_avi)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    print("Rendering customer demo slides...")
    slides = [_render_scene(scene, index, build_avi) for index, scene in enumerate(SCENES)]
    print("Synthesizing voiceover...")
    scene_audio = [_synthesize_scene(scene, index) for index, scene in enumerate(SCENES)]
    total_audio_samples = _write_combined_wav(scene_audio)
    if ENCODER in {"auto", "ffmpeg"} and shutil.which("ffmpeg"):
        print("Recording narrated WebM with ffmpeg slideshow encoder...")
        _record_webm_with_ffmpeg(SCENES, scene_audio)
    elif ENCODER == "ffmpeg":
        raise SystemExit("ffmpeg is required when TIJARA_CUSTOMER_DEMO_ENCODER=ffmpeg")
    else:
        print("Recording narrated WebM with Chrome MediaRecorder...")
        _record_webm_with_browser(SCENES, scene_audio)
    if build_avi:
        print("Writing optional narrated AVI...")
        total_frames, total_audio_samples = _write_avi(slides, scene_audio)
        print("Intermediate narrated AVI written to %s" % OUTPUT_AVI)
    duration = total_audio_samples / SAMPLE_RATE
    print("Customer demo video written to %s" % OUTPUT_WEBM)
    print("Voiceover WAV written to %s" % OUTPUT_WAV)
    print("duration_seconds=%.1f" % duration)


if __name__ == "__main__":
    main()
