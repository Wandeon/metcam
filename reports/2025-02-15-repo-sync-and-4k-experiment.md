# FootballVision Pro – Repository Alignment & 4K Experimental Pipeline

_Date:_ 2025-02-15
_Author:_ Codex (GPT-5 in CLI)

---

## Summary
- **Repository realigned** with the production Jetson Orin Nano device that recently captured a match. The authoritative recording pipeline is now the shell-based `record_dual_1080p30.sh` companioned by Python orchestration (no C++/NVENC remnants).
- **Dashboard and API** updated to reflect current capabilities (no automatic side-by-side merging; recordings presented as per-camera segments only).
- **Experimental GPU pipeline** added (`record_dual_4k30_rotated.sh`) to explore 4K30 capture with 30% centre cropping and per-camera ±20° rotations via GLSL shaders.

---

## Device vs. Repository Reconciliation

### Previous State
- Repo contained stubbed C++ NVENC pipeline (`gstreamer-core`, `nvenc-integration`) that never emitted frames.
- On-device `/home/mislav/footballvision` tree was running a robust shell + Python workflow that successfully recorded matches at 1080p30 using software `x264enc`.
- Web dashboard still exposed buttons and copy for side-by-side merge/upload flows that no longer existed in practice.

### Actions Taken
1. **Removed legacy modules**: deleted C++/NVENC code, build scripts, and outdated docs from `src/video-pipeline/`.
2. **Migrated production scripts**: copied `record_dual_1080p30.sh`, `record_test_simple.sh`, and `merge_segments.sh` into the repo; rewrote `recording_manager.py` to match the device controller (PID tracking, manifest generation, no merge triggers).
3. **Doc refresh**:
   - `README.md`, `DEPLOYMENT.md`, `docs/development/setup.md`, `integration-map.json` now describe the real shell-based pipeline.
   - Contributor guide updated previously with accurate references.
4. **Dashboard cleanup**: `Matches` page now lists per-camera segments only; removed processing/upload buttons and side-by-side hints.

---

## Experimental 4K Rotated Pipeline

### Goal
Explore a GPU-accelerated path that:
- Captures the full 4K sensor feed (mode 0, 3840×2160@30).
- Applies a 30% centre crop (keeping 70% of the FOV).
- Rotates Camera 0 by -20° (counter-clockwise) and Camera 1 by +20° (clockwise) **before** encoding.

### Implementation
- Added GLSL fragment shaders (`src/video-pipeline/shaders/rotate_crop_ccw20.frag`, `rotate_crop_cw20.frag`) that perform crop + rotation on NVMM textures.
- Created `scripts/record_dual_4k30_rotated.sh` which:
  - Uses `nvarguscamerasrc` (sensor-mode 0) → `nvvidconv` → `glupload` → `glshader` (custom shader) → `gldownload` → `x264enc`.
  - Encodes to `cam0_rot_*.mp4` and `cam1_rot_*.mp4` in `/mnt/recordings/<match>/segments/`.
  - Logs to `recording_rotated.log` per match.
  - Maintains the existing 1080p script untouched.
- Documentation updated to flag the script as experimental.

### Limitations & Risks
- **CPU load**: Software `x264enc` at 4K30 (even post-crop) is near the limits of the Jetson CPU. Expect high usage and potential frame drops; hardware NVENC is still absent in JetPack 6.x.
- **GL stack requirements**: `glupload`, `glshader`, and `gldownload` demand working EGL + GPU drivers. Ensure `gst-plugins-bad` with GL support is installed and no headless display constraints exist.
- **Future maintainability**: Custom shaders add complexity. If this path evolves, consider encapsulating the pipeline in a robust Python wrapper with error recovery.

### Next Steps for Testing
1. Validate GL availability:
   ```bash
   gst-inspect-1.0 glshader
   export GST_GL_PLATFORM=egl  # if running headless
   ```
2. Dry run on staging Jetson (short recording, monitor `htop` and `nvidia-smi`).
3. Review encoded clips for rotation accuracy and cropping boundaries.
4. Gather metrics (frame drops, CPU/GPU utilisation) to decide whether to pursue optimization or return to 1080p baseline.

---

## Open Questions / Decisions Needed
- Do we continue investing in the GPU-based rotation pipeline, or should we wait for hardware NVENC support (JetPack 5.x or future releases)?
- Should `recording_manager.py` expose a flag/API to pick between 1080p baseline and the 4K experimental path?
- Do we remove `merge_segments.sh` entirely, or keep it as a manual utility for after-game processing?

---

## Repository Snapshot (key files added/changed)
- `scripts/record_dual_1080p30.sh` – authoritative 1080p pipeline.
- `scripts/record_dual_4k30_rotated.sh` – experimental GL-driven pipeline.
- `src/video-pipeline/recording_manager.py` – production controller (no auto-merge).
- `src/video-pipeline/preview_service.py` – unchanged core preview service.
- `src/platform/web-dashboard/src/pages/Matches.tsx` – UI aligned with real workflow.
- `DEPLOYMENT.md`, `docs/development/setup.md`, `integration-map.json`, `src/video-pipeline/README.md` – documentation refresh.

---

## What to Expect Going Forward
- **Production path** remains 1080p@30 per camera with stable CPU load and HLS preview.
- **Experimental path** may offer increased visual fidelity with pre-encoder rotation, but requires performance tuning and validation. Expect iterative cycles.
- All future contributors should build on the shell + Python approach; any reintroduction of C++ pipelines should come with tested GPU encode paths (e.g., once NVENC becomes viable again).

---

_This report will be updated as tests for the 4K rotated pipeline conclude or as JetPack/NVENC availability changes._
