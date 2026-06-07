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


SCENES = [
    {
        "slug": "intro",
        "eyebrow": "Pakistan-focused open-source retail suite",
        "title": "Tijara Suite",
        "subtitle": "POS, inventory, restaurant, analytics, SaaS control, and hardware readiness on Odoo Community.",
        "bullets": [
            "Built for superstores, groceries, bakeries, restaurants, pharmacies, garments, cloth, electronics, and wholesale.",
            "Urdu-ready operations, barcode workflows, customer display, queue, kiosk, and back-office controls.",
            "Open-source-first foundation for community adoption and enterprise deployment.",
        ],
        "metric": "Enterprise SaaS foundation",
        "voiceover": (
            "Meet Tijara Suite, an open-source-first business platform for Pakistan. "
            "It brings point of sale, inventory, restaurant service, customer displays, analytics, and back-office controls "
            "into one Odoo Community based suite that can grow from one shop to a multi-tenant SaaS rollout."
        ),
    },
    {
        "slug": "pos",
        "eyebrow": "Fast cashier workflow",
        "title": "Touch-friendly POS for B2C and B2B",
        "subtitle": "Cashiers can sell retail or wholesale, scan barcodes, apply controlled discounts, and print receipts.",
        "bullets": [
            "Separate B2C and B2B prices on inventory products.",
            "Overall bill discount by percentage or fixed amount with automatic sync.",
            "Refund and exchange flow using invoice barcode scan.",
        ],
        "metric": "Checkout, refund, and print",
        "voiceover": (
            "At the counter, cashiers get a touch-friendly POS. They can scan products, switch between B2C and B2B pricing, "
            "apply an overall bill discount by amount or percentage, print a receipt, and process returns by scanning the invoice barcode."
        ),
    },
    {
        "slug": "restaurant",
        "eyebrow": "Restaurant and bakery operations",
        "title": "Dine-in, takeaway, pickup, and kiosk",
        "subtitle": "Restaurant teams can run self-ordering, queue tickets, kitchen status, menu boards, and deals displays.",
        "bullets": [
            "Kiosk checkout supports dine-in, takeaway, and pickup.",
            "Queue display shows waiting, preparing, ready, and called orders.",
            "Menu, deals, and promotion screens can be enabled per SaaS plan.",
        ],
        "metric": "Kiosk plus queue system",
        "voiceover": (
            "For restaurants and bakeries, Tijara supports dine-in, takeaway, and pickup. "
            "Customers can order from a kiosk, teams can manage queue tickets and kitchen status, and managers can publish menu, deal, and promotion screens."
        ),
    },
    {
        "slug": "inventory",
        "eyebrow": "Inventory intelligence",
        "title": "Stock, expiry, racks, shelves, and bulk data",
        "subtitle": "Inventory managers get alerts and location-aware records for daily retail control.",
        "bullets": [
            "Low-stock and expiry alerts for perishable, pharmacy, grocery, and bakery items.",
            "Warehouse, store, rack, shelf, bin, and product placement metadata.",
            "CSV import and export for products, prices, contacts, stock, and devices.",
        ],
        "metric": "Low stock and expiry alerts",
        "voiceover": (
            "Inventory teams can manage stock with low-stock and expiry alerts, storage positions, racks, shelves, bins, and warehouse locations. "
            "Bulk import and export keeps product, price, contact, stock, hardware, and promotion data easy to maintain."
        ),
    },
    {
        "slug": "customer-experience",
        "eyebrow": "Customer-facing screens",
        "title": "Displays that sell and guide",
        "subtitle": "Customer display, queue, menu, deals, and promotion screens are controlled as SaaS features.",
        "bullets": [
            "Customer display publishes live cart lines, totals, and receipt context.",
            "Queue screen keeps pickup and service flow visible.",
            "Promotions and deals help stores run campaigns from the back office.",
        ],
        "metric": "SaaS feature flags",
        "voiceover": (
            "Customer experience features are plan controlled. Businesses can enable customer display, queue display, promotion boards, menu boards, and deal screens only where the tenant has subscribed."
        ),
    },
    {
        "slug": "back-office",
        "eyebrow": "Back office and compliance",
        "title": "Purchasing, payments, FBR, and finance evidence",
        "subtitle": "Operators can prepare subscription billing, PSP settlement review, refunds, chargebacks, and FBR submission queues.",
        "bullets": [
            "JazzCash, Easypaisa, Stripe, and generic PSP readiness foundations.",
            "Settlement, refund, chargeback, and draft accounting action records.",
            "FBR queue adapter foundation with dry-run and live-mode guardrails.",
        ],
        "metric": "Finance and compliance control",
        "voiceover": (
            "The back office foundation covers subscription billing, payment webhooks, settlement reconciliation, refunds, chargebacks, draft accounting actions, and FBR queue readiness, with clear audit records for finance and compliance teams."
        ),
    },
    {
        "slug": "analytics",
        "eyebrow": "Enterprise dashboards",
        "title": "Trends, history, reports, and release confidence",
        "subtitle": "Owners see sales, inventory, queue, promotion, operations, and release-readiness evidence in one workflow.",
        "bullets": [
            "Daily KPI collectors feed dashboards, charts, reports, and history.",
            "Protected release gates collect evidence for QA, security, DevOps, and business owners.",
            "Deployment docs, monitoring, backups, rollback, and runbooks are maintained for production readiness.",
        ],
        "metric": "Analytics plus release gates",
        "voiceover": (
            "Owners and operators get analytics for sales, inventory, queues, promotions, and operational history. "
            "For enterprise delivery, Tijara also includes protected release evidence, monitoring notes, backup drills, rollback guidance, and deployment runbooks."
        ),
    },
    {
        "slug": "closing",
        "eyebrow": "Ready for pilots and community growth",
        "title": "A modular suite for Pakistani businesses",
        "subtitle": "Start with the needed vertical, enable features per tenant, and keep the foundation open-source friendly.",
        "bullets": [
            "Deployable to superstores, pharmacies, restaurants, garments, electronics, groceries, cloth shops, and bakeries.",
            "Features can be enabled or disabled per SaaS plan.",
            "Built to mature into an enterprise production-ready product with real certification evidence.",
        ],
        "metric": "Public repo friendly",
        "voiceover": (
            "Tijara Suite is designed for pilots today and enterprise maturity over time. "
            "It gives Pakistani businesses a modular, open-source-friendly platform that can be deployed by vertical, controlled by SaaS plan, and hardened with real production evidence."
        ),
    },
]


def _run(command):
    subprocess.run(command, check=True)


def _build_avi_enabled():
    return os.environ.get("TIJARA_CUSTOMER_DEMO_BUILD_AVI", "").strip().lower() in {"1", "true", "yes", "on"}


def _require_tools(build_avi):
    missing = []
    for tool in ["say", "afconvert", "node"]:
        if not shutil.which(tool):
            missing.append(tool)
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


def _scene_html(scene, index):
    bullets = "\n".join("<li>%s</li>" % html.escape(item) for item in scene["bullets"])
    accent = ["#1f7a8c", "#0f766e", "#b45309", "#2563eb", "#7c3aed", "#be123c", "#334155", "#047857"][index % 8]
    card_rows = "\n".join(
        '<div class="row"><span>%s</span><strong>%s</strong></div>'
        % (html.escape(label), html.escape(value))
        for label, value in [
            ("POS", "B2C/B2B"),
            ("Inventory", "Expiry alerts"),
            ("Display", "Queue live"),
            ("SaaS", "Feature flags"),
        ]
    )
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
    font-size: 43px;
    line-height: 1.05;
    margin: 0 0 12px;
    letter-spacing: 0;
  }}
  .subtitle {{
    font-size: 19px;
    line-height: 1.36;
    color: #4b5563;
    margin-bottom: 22px;
  }}
  ul {{
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 10px;
  }}
  li {{
    font-size: 17px;
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
    padding: 20px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    background: #fbfcfe;
  }}
  .metric {{
    grid-column: span 2;
    border-left: 5px solid {accent};
    background: #fff;
    border-radius: 8px;
    padding: 16px;
    font-size: 24px;
    font-weight: 850;
  }}
  .tile {{
    min-height: 86px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 14px;
    background: #fff;
  }}
  .tile small {{
    display: block;
    color: #64748b;
    font-weight: 700;
    margin-bottom: 8px;
  }}
  .tile strong {{
    font-size: 22px;
  }}
  .row {{
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid #eef2f7;
    padding: 9px 0;
    font-size: 15px;
  }}
  .row:last-child {{ border-bottom: 0; }}
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
      <div class="topbar"><div class="dots"><span></span><span></span><span></span></div><div>{html.escape(scene["slug"]).replace("-", " ").title()}</div></div>
      <div class="screen">
        <div class="metric">{html.escape(scene["metric"])}</div>
        <div class="tile"><small>Today</small><strong>PKR 284K</strong></div>
        <div class="tile"><small>Orders</small><strong>412</strong></div>
        <div class="tile" style="grid-column: span 2;">{card_rows}</div>
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


def _record_webm_with_browser(scenes, scene_audio):
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
