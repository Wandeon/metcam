# Recording Regression Matrix (Hardware-in-Loop)

This matrix validates recording stability across quality presets on a live metcam node.

## What It Covers

For each preset (`fast`, `balanced`, `high`), the runner:

1. Sets `recording_quality` in `config/camera_config.json`.
2. Restarts `footballvision-api-enhanced`.
3. Starts a real recording.
4. Samples CPU (`/api/v1/system-metrics`) during capture.
5. Stops recording and checks stop/integrity response.
6. Probes produced segments with `ffprobe` and extracts effective FPS.
7. Writes a structured JSON report and returns non-zero when thresholds fail.

## Local Run (on metcam)

```bash
cd /home/mislav/footballvision-pro
python3 scripts/run_recording_regression_matrix.py \
  --api-base-url http://localhost:8000/api/v1 \
  --duration-seconds 20 \
  --min-fps 24 \
  --max-cpu-p95 95
```

Output report:

- `artifacts/recording-regression/recording-matrix-<UTC>.json`

## GitHub Workflow

Workflow file: `.github/workflows/hardware-regression-matrix.yml`

- `schedule`: nightly (`02:30 UTC`)
- `workflow_dispatch`: manual run with threshold/duration inputs
- runner target: `[self-hosted, linux, arm64, metcam]`

## Interpreting Results

Each preset result contains:

- `start_response` and `stop_response`
- `camera_metrics.camera_0|camera_1.stop` and `.probe`
- `cpu_summary` (`avg`, `p95`, `max`, sample count)
- `pass` and explicit `failures[]`

Common failure signals:

- `stop_failed:*` - stop API did not report success
- `integrity_not_all_ok` - integrity gate failed
- `camera_X_probe_failed:*` - ffprobe failed or no segment
- `camera_X_fps_low:*` - effective FPS below `--min-fps`
- `cpu_p95_high:*` - CPU p95 above `--max-cpu-p95`

## Safety / Restore Behavior

- The runner restores the original `camera_config.json` at the end.
- The runner restarts the API after restoring config.
- The runner force-stops any active recording during cleanup.
