# FootballVision Pro – 4K Rotation Experiment Progress

_Date:_ 2025-02-15
_Author:_ Codex (GPT-5 in CLI)

## Objective
Apply a 30% centre crop and ±20° per-camera rotation **before** encoding, while capturing 4K@30 fps from the IMX477 sensors on the Jetson Orin Nano. Preserve the production 1080p pipeline and prototype an alternate GPU-backed workflow (`record_dual_4k30_rotated.sh`).

## Work Completed
- Ported the on-device 1080p scripts and controller to the repository; removed non-functional C++/NVENC code.
- Introduced GLSL shaders (`rotate_crop_ccw20.frag`, `rotate_crop_cw20.frag`) executed via `glshader` to perform crop + rotation.
- Built `record_dual_4k30_rotated.sh` to capture sensor mode 0, push frames through `glupload → glshader → gldownload`, and encode with `x264enc` at a high target bitrate.
- Iteratively refined the pipeline:
  - Adjusted caps so `glupload` accepts the converted RGBA frames.
  - Reworked shaders to use GL-compatible syntax; injected shader source inline for `glshader`.
  - Added `RECORD_SECONDS` / `SEGMENT_SECONDS` knobs for deterministic short tests.
  - Improved cleanup to send SIGINT, wait for EOS, and disable async mux finalization.
  - Tuned x264 via `option-string` (CBR hints, VBV sizing, forced CFR).
- Executed multiple 10 s runs for validation (match IDs `match_4k_test8`–`match_4k_test15`, `match_4k_cam1_test`, etc.). All experimental directories were removed from `/mnt/recordings` once analysis concluded.

## Obstacles Encountered
1. **Shader Integration**
   - Initial `glshader` usage failed because the `fragment` property expects inline GLSL, not file paths. Corrected by reading shader text at runtime.
   - `glupload` cannot ingest NVMM RGBA buffers directly; conversion to CPU RGBA is required before uploading to the GL pipeline.
   - GLSL versioning: Jetson’s GL stack rejected `#version 300 es`; reverting to legacy syntax (`gl_FragColor`, `varying`) resolved compilation errors.

2. **Process Lifecycle**
   - Two independent `gst-launch-1.0` processes meant we had to manage PIDs explicitly. Early reliance on `pkill` prevented `splitmuxsink` from finalizing MP4 headers.
   - Cleanup now delivers SIGINT, waits for each process, and uses synchronous finalize, but rapid shutdown still risks truncated containers.

3. **Encoder Constraints**
   - Jetson’s `x264enc` omits certain properties (e.g., `vbv-maxrate`) requiring `option-string`. Even with CBR hints, CPU limits keep effective bitrates around 7–9 Mb/s—far below the requested 90 Mb/s.

4. **Container Finalization**
   - Despite synchronous finalize, short captures regularly miss the MP4 `moov` atom (`ffprobe: moov atom not found`). The muxer likely exits before writing headers when the pipeline is interrupted quickly.

## Current Status (2025-02-15 @ 16:55)
- Production 1080p pipeline remains untouched and reliable.
- Experimental pipeline successfully rotates/crops frames and produces H.264 payloads, but resulting MP4s are still non-playable due to missing headers.
- `/mnt/recordings` is clean aside from pre-existing production content (`6kolo`, `Probna`, `test_10s`).

## Next Steps
1. Replace `splitmuxsink` with `mp4mux ! filesink` (single segment) or use Matroska for short tests to guarantee valid containers.
2. Run longer captures (≥60 s) to measure sustained CPU/GPU load and confirm x264 stability.
3. Investigate hardware-assisted encoding (downgrade to JetPack 5.x for NVENC or package alternative encoders) if 4K30 software encode proves unreliable.
4. Consider consolidating both cameras into a single GStreamer pipeline or a Python wrapper to better coordinate EOS and mux finalization.

## Key Takeaways
- Arbitrary-angle rotation via GLSL is achievable but demands careful handling of GL contexts and shader syntax on Jetson.
- Software x264 cannot realistically deliver “near-lossless” 4K30 under these conditions; hardware encoding remains a gating factor.
- Short-duration tests must ensure muxers finalize; otherwise, we generate non-renderable assets despite successful capture logs.

---
This report supplements the earlier repository-alignment notes and captures the current state of the 4K rotation experiment as of 16:55.
