#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIP_DIR="$ROOT_DIR/docs/video-clips"
OUTPUT="$ROOT_DIR/docs/PRODUCT_DEMO.mp4"
FILELIST="$CLIP_DIR/filelist.txt"

mkdir -p "$CLIP_DIR"
: >"$FILELIST"

find "$CLIP_DIR" -maxdepth 1 -type f -name "*.webm" | sort | while read -r clip; do
    printf "file '%s'\n" "$clip" >>"$FILELIST"
done

if [ ! -s "$FILELIST" ]; then
    echo "No .webm clips found under docs/video-clips."
    echo "Run node scripts/record-demo.js against a live dev or staging instance first."
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg is not installed. File list written to $FILELIST."
    echo "Install ffmpeg, then run: ffmpeg -f concat -safe 0 -i $FILELIST -c copy $OUTPUT"
    exit 0
fi

ffmpeg -f concat -safe 0 -i "$FILELIST" -c copy "$OUTPUT"
echo "Demo video written to $OUTPUT"
