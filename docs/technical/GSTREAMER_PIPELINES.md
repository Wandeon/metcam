# GStreamer Pipeline Reference (v3 Architecture)

## Overview

FootballVision Pro v3 runs both recording and preview pipelines fully in-process via Python/GStreamer bindings. The pipelines share the same deterministic crop path and differ only in encoder settings and sinks. This document captures the current production configuration.

## Environment

- **Hardware**: NVIDIA Jetson Orin Nano (8 GB)
- **JetPack**: 6.1 (Ubuntu 22.04, L4T R36.4.4)
- **Cameras**: Dual Sony IMX477 (sensor mode 0)
- **GStreamer**: 1.20+ with NVIDIA multimedia plugins
- **Runtime**: In-process GLib main loop managed by `GStreamerManager`

## Recording Pipeline (Per Camera)

```bash
nvarguscamerasrc name=src sensor-mode=0 sensor-id={CAM_ID} \
    tnr-mode=0 ee-mode=0 wbmode=1 aelock=false \
    exposuretimerange="13000 33000000" gainrange="1 16" \
    ispdigitalgainrange="1 4" saturation=1.0 ! \
  video/x-raw(memory:NVMM),format=NV12,width=3840,height=2160,framerate=30/1 ! \

  # NVMM → system memory (no crop in hardware to avoid chroma issues)
  nvvidconv ! \
  video/x-raw,format=NV12,width=3840,height=2160,framerate=30/1 ! \

  # Deterministic software crop using CPU
  videocrop left=480 right=480 top=272 bottom=272 ! \
  video/x-raw,format=NV12,width=2880,height=1616,framerate=30/1,colorimetry=bt709,interlace-mode=progressive ! \

  # NV12 → I420 before software x264
  videoconvert ! \
  video/x-raw,format=I420,width=2880,height=1616,framerate=30/1,colorimetry=bt709,interlace-mode=progressive ! \

  # H.264 encoding (12 Mbps, IDR every 60 frames)
  x264enc name=enc speed-preset=ultrafast tune=zerolatency \
          bitrate=12000 key-int-max=60 b-adapt=false bframes=0 \
          aud=true byte-stream=false option-string=repeat-headers=1:scenecut=0:open-gop=0 ! \

  h264parse config-interval=-1 disable-passthrough=true ! \
  video/x-h264,stream-format=avc ! \

  # MP4 segments (10 minutes each)
  splitmuxsink name=sink max-size-time=600000000000 muxer-factory=mp4mux \
               async-finalize=true \
               location=/mnt/recordings/{MATCH_ID}/segments/cam{CAM_ID}_{TS}_%02d.mp4
```

- `TS` is a timestamp (`YYYYMMDD_HHMMSS`) injected by `RecordingService`.
- Segments roll every 10 minutes; all files are MP4 to simplify downstream tooling.

## Preview Pipeline (Per Camera)

```bash
nvarguscamerasrc name=src sensor-mode=0 sensor-id={CAM_ID} \
    tnr-mode=0 ee-mode=0 wbmode=1 aelock=false \
    exposuretimerange="13000 33000000" gainrange="1 16" \
    ispdigitalgainrange="1 4" saturation=1.0 ! \
  video/x-raw(memory:NVMM),format=NV12,width=3840,height=2160,framerate=30/1 ! \

  nvvidconv ! \
  video/x-raw,format=NV12,width=3840,height=2160,framerate=30/1 ! \

  videocrop left=480 right=480 top=272 bottom=272 ! \
  video/x-raw,format=NV12,width=2880,height=1616,framerate=30/1,colorimetry=bt709,interlace-mode=progressive ! \

  videoconvert ! \
  video/x-raw,format=I420,width=2880,height=1616,framerate=30/1,colorimetry=bt709,interlace-mode=progressive ! \

  # Lower bitrate encoder tuned for streaming
  x264enc name=enc speed-preset=ultrafast tune=zerolatency \
          bitrate=3000 key-int-max=60 b-adapt=false bframes=0 \
          byte-stream=true aud=true intra-refresh=false \
          option-string=repeat-headers=1:scenecut=0:open-gop=0 ! \

  h264parse config-interval=1 disable-passthrough=true ! \
  video/x-h264,stream-format=byte-stream ! \

  # HLS segments (2 seconds, tmpfs)
  hlssink2 name=sink \
           playlist-location=/dev/shm/hls/cam{CAM_ID}.m3u8 \
           location=/dev/shm/hls/cam{CAM_ID}_%05d.ts \
           target-duration=2 playlist-length=8 max-files=8 \
           send-keyframe-requests=true
```

- `PreviewService` exposes the streams at `/hls/cam0.m3u8` and `/hls/cam1.m3u8`.
- Segments are stored in `/dev/shm/hls` (tmpfs) to avoid flash wear.

## Recording vs Preview – Key Differences

| Aspect            | Recording                             | Preview                              |
|-------------------|---------------------------------------|--------------------------------------|
| Bitrate           | 12 Mbps                               | 3 Mbps                               |
| Stream format     | `byte-stream=false` (AVC)             | `byte-stream=true`                   |
| h264parse config  | `config-interval=-1`                  | `config-interval=1`                  |
| Output            | `splitmuxsink` → MP4 (10‑minute cuts) | `hlssink2` → 2 s TS segments         |
| Segment path      | `/mnt/recordings/<match>/segments/`    | `/dev/shm/hls/`                      |
| File naming       | `cam{N}_{TS}_%02d.mp4`                | `cam{N}_%05d.ts`                     |

Both pipelines share the exact crop, color, and encoder parameter chain, ensuring that what you preview is exactly what you record.

## Default Camera Configuration

Source of truth: `config/camera_config.json`

```json
{
  "rotation": 0.0,
  "crop": { "left": 480, "right": 480, "top": 272, "bottom": 272 },
  "correction_type": "barrel",
  "correction_params": { "k1": 0.0, "k2": 0.0 }
}
```

- Final resolution: 2880 × 1616 (56 % field of view from the 4K sensor).
- Both cameras start with identical trims; asymmetry can be introduced via the camera configuration API/UI.

## Runtime Characteristics

- **Start latency**: ~100 ms for both recording and preview (no subprocesses).
- **Stop latency**: ~2 s (EOS drain with splitmuxsink finalisation).
- **CPU usage**: ~40 % total during dual recording (software x264 dominates).
- **Preview**: Adds ~8 % CPU per camera when running alongside recording.
- **State persistence**: `RecordingService` stores `/tmp/footballvision_recording_state.json`; pipelines are rehydrated post-restart when possible.

## Troubleshooting Tips

### Caps Negotiation Errors
- Ensure each transformation stage specifies explicit caps (see pipeline listings above).
- Keep memory types consistent: NVMM upstream, system memory downstream of the first `nvvidconv`.

### Chroma/Color Anomalies
- Do **not** re-enable hardware cropping via `nvvidconv compute-hw`. Hardware cropping reintroduces the teal/cyan corruption that v3 resolved.
- Stick with `videocrop` in system memory; this is the validated path.

### Unexpected Preview Paths
- Preview segments live in `/dev/shm/hls`. If you need to serve them from `/tmp/hls`, create a bind mount or adjust the API mount point.

### Inspecting Pipelines

```bash
# Quick sanity check with video sink
gst-launch-1.0 -e \
  nvarguscamerasrc sensor-mode=0 sensor-id=0 ! \
  video/x-raw(memory:NVMM),format=NV12,width=3840,height=2160,framerate=30/1 ! \
  nvvidconv ! \
  video/x-raw,format=NV12,width=3840,height=2160,framerate=30/1 ! \
  videocrop left=480 right=480 top=272 bottom=272 ! \
  videoconvert ! \
  autovideosink sync=false

# Inspect element capabilities
gst-inspect-1.0 nvarguscamerasrc | grep sensor-mode
gst-inspect-1.0 nvvidconv | grep -E \"left|right|top|bottom\"
gst-inspect-1.0 x264enc | grep bitrate
```

## References

- `src/video-pipeline/pipeline_builders.py`
- `src/video-pipeline/gstreamer_manager.py`
- `src/video-pipeline/recording_service.py`
- `src/video-pipeline/preview_service.py`
- `config/camera_config.json`

## Changelog

- **2025‑10‑24 – Finalised CPU Crop Path**  
  Replaced GPU/VIC cropping with a software `videocrop` stage to resolve chroma corruption and mismatched HLS output. Recording and preview now share a single deterministic chain and expose identical framing.
