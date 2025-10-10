#!/bin/bash
# Merge 5-minute segments into full match videos

MATCH_ID=$1
SEGMENTS_DIR="/mnt/recordings/${MATCH_ID}/segments"
OUTPUT_DIR="/mnt/recordings/${MATCH_ID}"

if [ ! -d "$SEGMENTS_DIR" ]; then
    echo "Error: Segments directory not found"
    exit 1
fi

echo "Merging segments for match: $MATCH_ID"

# Merge Camera 0
ls $SEGMENTS_DIR/cam0_*.mp4 | sort | sed 's/^/file /' > /tmp/cam0_concat.txt
ffmpeg -f concat -safe 0 -i /tmp/cam0_concat.txt -c copy "$OUTPUT_DIR/camera0_full.mp4"

# Merge Camera 1
ls $SEGMENTS_DIR/cam1_*.mp4 | sort | sed 's/^/file /' > /tmp/cam1_concat.txt
ffmpeg -f concat -safe 0 -i /tmp/cam1_concat.txt -c copy "$OUTPUT_DIR/camera1_full.mp4"

echo "Merge complete. Output files:"
ls -lh $OUTPUT_DIR/*.mp4
