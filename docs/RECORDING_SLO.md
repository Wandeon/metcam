# Recording SLO and Alert Runbook

Version: `v1.0`  
Last updated: `2026-02-12`

## SLO Targets

These targets define acceptable recording reliability/quality for production operation.

1. **Stop transport reliability**
   - Target: `transport_success=true` in **>= 99.0%** of stop operations.
2. **Media integrity reliability**
   - Target: `integrity.all_ok=true` in **>= 99.0%** of stop operations.
3. **Effective per-camera FPS**
   - Target: each camera probe >= `recording_slo_min_effective_fps` (default `24.0`).
4. **Runtime overload containment**
   - Target: overload guard triggers should be rare and investigated immediately.

## Alert Signals (Operator Hooks)

The API runtime writes structured JSON events to:

- `/var/log/footballvision/system/alerts.log`

And exposes them via:

- `GET /api/v1/logs/alerts?lines=N`

Event types:

- `recording_overload_guard_triggered`
- `recording_stop_non_graceful`
- `recording_stop_transport_failure`
- `recording_integrity_failed`
- `recording_fps_below_slo`

## Key Endpoints for Triage

- `GET /api/v1/recording`
- `GET /api/v1/recording-health`
- `GET /api/v1/diagnostics/recording-correlations`
- `GET /api/v1/system-metrics`
- `GET /api/v1/logs/alerts?lines=200`
- `GET /api/v1/logs/health?lines=200`

## Runbook

1. **Confirm active symptoms**
   - Check `recording`, `degraded`, and `overload_guard` from `GET /api/v1/recording`.
2. **Inspect recent alert events**
   - Pull recent `alerts` log lines and identify event type bursts.
3. **Validate recording health**
   - Review `GET /api/v1/recording-health` issues per camera.
4. **Correlate low-level allocator faults**
   - Use `GET /api/v1/diagnostics/recording-correlations` for `NvVIC` + timeout/probe links.
5. **Collect performance evidence**
   - Run `scripts/run_recording_regression_matrix.py` and attach report JSON.
6. **Decide action**
   - If transport failures persist: rollback with `deploy/deploy-safe.sh` (automatic rollback path on failure).
   - If only overload/fps alerts: tune recording preset/thresholds and re-run matrix.

## Configuration Knobs

Defined in `config/camera_config.json`:

- `recording_slo_min_effective_fps`
- `recording_overload_guard_enabled`
- `recording_overload_cpu_percent_threshold`
- `recording_overload_poll_interval_seconds`
- `recording_overload_unhealthy_streak_threshold`
