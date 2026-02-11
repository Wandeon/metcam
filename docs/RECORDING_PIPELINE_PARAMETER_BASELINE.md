# Recording Pipeline Parameter Baseline (Jetson Orin Nano)

Updated: 2026-02-11

This document captures the current recording pipeline exactly as deployed and measured, before optimization work.

## 1. Scope and Fingerprint

- Repo: `Wandeon/metcam`
- Local analysis branch: `research/recording-pipeline-optimization-baseline`
- Device checked: `mislav@metcam`
- Device repo state during measurement: `main` at `1122fce`
- API service: `footballvision-api-enhanced.service` (active during all tests)
- Power mode during tests:
  - `sudo nvpmodel -q` -> `MAXN_SUPER`
  - `sudo jetson_clocks --show` -> performance governor on all CPUs

## 2. Source-of-Truth Files

- Pipeline builder: `src/video-pipeline/pipeline_builders.py:145` to `src/video-pipeline/pipeline_builders.py:247`
- Recording orchestration: `src/video-pipeline/recording_service.py:31` to `src/video-pipeline/recording_service.py:739`
- GStreamer stop/EOS handling: `src/video-pipeline/gstreamer_manager.py:244` to `src/video-pipeline/gstreamer_manager.py:352`
- Runtime config: `config/camera_config.json:4` to `config/camera_config.json:13`, `config/camera_config.json:17` to `config/camera_config.json:42`

## 3. Recording Pipeline: Full Parameter Inventory

Per-camera chain built by `build_recording_pipeline()`:

1. `nvarguscamerasrc`:
   - `sensor-mode=0`
   - `sensor-id={camera_id}`
   - `tnr-mode=1`
   - `ee-mode=1`
   - `wbmode=1`
   - `aelock=false`
   - `aeantibanding=3`
   - `exposurecompensation={from camera_config}`
   - `exposuretimerange="13000 33000000"`
   - `gainrange="1 16"`
   - `ispdigitalgainrange="1 1"`
   - `saturation=1.0`

2. Sensor caps:
   - `video/x-raw(memory:NVMM),width=3840,height=2160,format=NV12`

3. Crop stage (`nvvidconv name=cropper`):
   - Config values are pixels removed from each edge.
   - Current config for both cameras:
     - `left=480`, `right=480`, `top=0`, `bottom=408`
   - Converted to `nvvidconv` coordinates:
     - `left=480`, `right=3360`, `top=0`, `bottom=1752`
   - Output dimensions after crop:
     - `2880x1752`

4. Post-crop caps:
   - `video/x-raw(memory:NVMM),format=NV12,width=2880,height=1752`

5. Color conversion:
   - `nvvidconv`
   - `video/x-raw,format=I420,width=2880,height=1752,colorimetry=bt709,interlace-mode=progressive`

6. Queue before encoder:
   - `queue name=preenc_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 leaky=downstream`

7. Encoder (`x264enc`) common knobs:
   - `threads=0` (auto)
   - `aud=true`
   - `byte-stream=false`
   - Preset-specific values below

8. Queue after encoder:
   - `queue name=postenc_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 leaky=downstream`

9. Parse + caps:
   - `h264parse config-interval=-1 disable-passthrough=true`
   - `video/x-h264,stream-format=avc`

10. Queue before mux:
    - `queue name=mux_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 leaky=downstream`

11. Segment sink:
    - `splitmuxsink name=sink`
    - `location={match}/segments/cam{N}_{timestamp}_%02d.mp4`
    - `max-size-time=600000000000` (600s segment roll)
    - `muxer-factory=mp4mux`
    - `async-finalize=true`

### 3.1 Preset-Specific Encoder Parameters

`recording_quality` is set in `config/camera_config.json` (current deployed default: `fast`).

| Preset | speed-preset | tune | psy-tune | bitrate (kbps) | key-int-max | bframes | b-adapt | option-string |
|---|---|---|---|---:|---:|---:|---|---|
| `fast` | `ultrafast` | `0` | `none` | 20000 | 90 | 3 | `true` | `repeat-headers=1:scenecut=0:open-gop=0:vbv-maxrate=20000:vbv-bufsize=40000` |
| `balanced` | `fast` | `0` | `film` | 22000 | 75 | 2 | `true` | `repeat-headers=1:scenecut=0:open-gop=0:ref=2:rc-lookahead=20:qpmin=18:qpmax=32:vbv-maxrate=22000:vbv-bufsize=44000` |
| `high` | `veryfast` | `0` | `film` | 25000 | 90 | 3 | `true` | `repeat-headers=1:scenecut=0:open-gop=0:ref=3:rc-lookahead=30:qpmin=18:qpmax=32:vbv-maxrate=25000:vbv-bufsize=50000` |

## 4. Recording Service Runtime Policy Parameters

From `recording_service.py` and `camera_config.json`:

- Dual-camera requirement:
  - `recording_require_all_cameras=true` -> partial starts are rolled back
- Recovery policy:
  - `recording_recovery_max_attempts=2`
  - `recording_recovery_backoff_seconds=1.0` (linear backoff, capped at 5s in code)
- Stop policy:
  - `recording_stop_eos_timeout_seconds=8.0`
  - Each camera stop is EOS-first; timeout forces `NULL` state
- Protection policy:
  - `protection_seconds=10.0` (no non-force stop before 10s)
- Segment health endpoint checks:
  - Existence/state checks
  - basic growth checks
  - does not decode/validate MP4 bitstream integrity

## 5. Measured Baseline Data (Real Device)

Benchmark run method:

- API endpoint control (`/api/v1/recording`, `/api/v1/recording-health`)
- 22s active recording window per preset
- `sudo timeout 24s tegrastats --interval 1000` capture
- ffprobe on generated `cam0` and `cam1` segment files
- Config restored to original (`recording_quality=fast`) after test

Raw data file copied from metcam:

- `/tmp/recording_baseline_results_v2_20260211_220102.jsonl`

### 5.1 Summary Matrix

| Preset | CPU avg% | CPU max% | GR3D avg% | VIC avg% | Stop graceful | Cam0 media result | Cam1 media result |
|---|---:|---:|---:|---:|---|---|---|
| `fast` | 83.7 | 96.5 | 0.0 | 93.2 | yes | valid, 21.04s, 631 frames, 29.99 fps, 17.57 Mbps | valid, 21.44s, 640 frames, 29.85 fps, 17.49 Mbps |
| `balanced` | 89.4 | 100.0 | 0.0 | 84.2 | no (cam0 EOS timeout) | file exists but ffprobe parse failed | valid but degraded: 30.35s, 310 frames, 10.25 fps, 1.86 Mbps |
| `high` | 83.6 | 100.0 | 0.0 | 68.1 | yes | valid but short/low throughput: 10.60s, 181 frames, 17.08 fps, 3.04 Mbps | valid but degraded: 23.52s, 452 frames, 19.26 fps, 2.62 Mbps |

### 5.2 Additional Runtime Evidence

- API file log (`/var/log/footballvision/api/api_v3.log`) shows repeated EOS timeout pattern across many runs:
  - Example for this benchmark: `bench_balanced_1770843710`, cam0 timeout at line around `17702`
  - Repeated historical timeouts also visible (multiple prior matches)
- Systemd service log shows VIC allocation/open failures around benchmark timeframe:
  - `failed to allocate buffer, error from allocation request`
  - `failed to open NvVIC 6`
- Storage throughput sanity check:
  - `dd` write test on `/mnt/recordings`: ~690 MB/s (not an obvious bottleneck for current bitrates)

## 6. Conclusions From Evidence

1. CPU is the primary limiter:
   - GR3D remains at 0% during recording for all presets.
   - CPU averages 84-89% with peaks to 100%.

2. Current preset ladder is not monotonic in real outcomes:
   - `fast` produced the best effective fps and valid files in this run.
   - `balanced` and `high` produced degraded or inconsistent outputs.

3. Stop-path fragility is real:
   - EOS timeout happens in real workloads (especially cam0 in measured runs).
   - Timeout + forced `NULL` correlates with invalid/truncated artifacts.

4. Health endpoint can return false confidence:
   - `recording-health` reported healthy before stop in runs where final media was degraded or unprobeable.

5. Queue policy likely trades integrity for liveness:
   - All critical queues use `leaky=downstream` with large time windows.
   - This avoids backpressure deadlocks but can silently drop data.

## 7. Documentation Drift (Needs Correction)

Current docs are inconsistent with deployed code and measured behavior:

- `src/video-pipeline/README.md` still describes pipeline components/settings not matching current builder output (for example crop geometry and encoder details).
- `README.md` architecture section still references older pipeline concepts in parts.

Any optimization work should treat `pipeline_builders.py`, `recording_service.py`, and this baseline document as primary truth.

## 8. Optimization Candidate Backlog (For Next PRs)

These are hypotheses only, prioritized for controlled testing:

1. Stabilize EOS close path first (highest priority):
   - Increase/segment stop timeout strategy beyond fixed 8s.
   - Add explicit mux/segment finalization checks before returning success.
   - Acceptance: no EOS timeout in 20+ consecutive stop cycles; no invalid MP4.

2. Revisit queue leak strategy:
   - Test non-leaky or tighter bounded queue behavior per stage.
   - Acceptance: no unprobeable files; fps variance reduced; no deadlocks.

3. Rebuild quality ladder from stable baseline (`fast`):
   - Tune one knob at a time (bitrate, GOP, bframes/lookahead) with A/B runs.
   - Acceptance: quality gain without fps collapse or integrity regressions.

4. Strengthen health checks:
   - Add optional lightweight probe validation of newest segment per camera.
   - Acceptance: health endpoint catches real corruption cases seen above.

5. Track VIC allocation failures during runs:
   - Correlate `NvVIC` errors with stop/integrity failures.
   - Acceptance: failure rate materially reduced after pipeline tuning.

## 9. Test Baseline Status (Code-Level)

Local test execution:

- Command:
  - `python3 -m unittest discover -s tests -p 'test_*.py'`
- Result:
  - `Ran 59 tests in 0.968s`
  - `OK`

Coverage includes builder/service contracts and stop semantics in stubs, but does not replace hardware-in-loop media integrity tests.

## 10. Guardrails Before Starting Optimization

Use these controls for each optimization experiment:

1. Keep one change per run (single variable).
2. Run at least `fast/balanced/high`-equivalent 3x repeats for statistical direction.
3. Collect for every run:
   - tegrastats (CPU/GR3D/VIC/EMC)
   - stop details (`graceful_stop`, per-camera timeout flags)
   - ffprobe decodeability + fps + duration + bitrate
4. Reject any change that increases invalid files or EOS timeout rate, even if average CPU drops.
