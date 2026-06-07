# Voiceover Recording Guide

## Recording Setup

- Record in a quiet room with a USB microphone or headset mic.
- Use Audacity, DaVinci Resolve, OBS, or another free recording tool.
- Record at 48 kHz, mono or stereo, with light noise reduction only.
- Keep the tone confident, practical, and product-demo focused.

## Pacing

- Leave one second of silence before and after each scene.
- Pause briefly after naming a workflow so the screen can catch up.
- Keep each sentence short enough to match the visual action.
- Re-record any scene where the narration feels rushed.

## Sync Workflow

1. Run `node scripts/record-demo.js` against a live dev or staging instance.
2. Run `bash scripts/assemble-video.sh` after clips are recorded.
3. Import `docs/PRODUCT_DEMO.mp4` and the voice recording into Audacity,
   DaVinci Resolve, or another editor.
4. Align each scene to the matching section in `docs/VIDEO_SCRIPT.md`.
5. Export final video as 1080p H.264 video with AAC audio at 48 kHz.

## Delivery

- Keep one silent MP4 for reuse by sales engineers.
- Keep one narrated MP4 for async demos.
- Export short persona-specific clips when pitching a single vertical such as
  restaurant, grocery, pharmacy, bakery, garments, electronics, or superstore.
