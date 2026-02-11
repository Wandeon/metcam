# Recording & Preview Baseline Fallback (Verified)

This document is the **safe fallback specification** for the current recording and preview system.
Use it to recover known-good behavior if future development introduces regressions.

## Baseline Fingerprint

- Repository: `Wandeon/metcam`
- Baseline commit: `6cd65539a4a8e5c3d3eab8d556158b4825ad7d75`
- Includes merged fixes:
  - WS command plane and `/ws` proxy support
  - Recording health endpoint
  - Stable CPU metrics (`psutil`)
  - Panorama capture exposure warmup
  - Preview stop hardening (non-EOS teardown)

## Scope

This fallback covers:

- Dual-camera recording pipeline
- Dual-camera HLS preview pipeline
- REST and WebSocket control paths
- Pipeline lock/mutex behavior
- Deployment and restore sequence on Jetson

## Runtime Topology

### Core services

- API: `src/platform/simple_api_v3.py` (`:8000`)
- GStreamer lifecycle manager: `src/video-pipeline/gstreamer_manager.py`
- Recording orchestration: `src/video-pipeline/recording_service.py`
- Preview orchestration: `src/video-pipeline/preview_service.py`
- Global mode lock: `src/video-pipeline/pipeline_manager.py`
- Caddy reverse proxy/static/HLS: `deploy/config/Caddyfile`

### Storage and stream paths

- Recordings: `/mnt/recordings/<match_id>/segments/*.mp4`
- Preview HLS: `/dev/shm/hls/cam0.m3u8`, `/dev/shm/hls/cam1.m3u8`
- HLS public route: `/hls/*` (served by Caddy from `/dev/shm`)

## Recording Pipeline Baseline

Defined by `build_recording_pipeline()` in `src/video-pipeline/pipeline_builders.py`.

Per camera flow:

1. `nvarguscamerasrc` (IMX477 3840x2160, NV12, NVMM)
2. `nvvidconv` crop (VIC hardware, bounding-box coordinates)
3. `nvvidconv` to CPU I420
4. `x264enc` (preset from `recording_quality`, default `high`)
5. `h264parse` (`stream-format=avc`)
6. `splitmuxsink` (`mp4mux`, 10-minute rotation)

### Quality presets

- `high`: `superfast`, film tune, 25 Mbps, `bframes=1`, `rc-lookahead=10`
- `balanced`: `superfast`, film tune, 22 Mbps, `bframes=1`, `rc-lookahead=10`
- `fast` (default): `ultrafast`, 20 Mbps, `bframes=0`, `rc-lookahead=0`

### Preset Stability Validation (Issue #34, 2026-02-11)

Retuned ladder validation on metcam (`ec92796`) using 20-25s dual-camera runs:

| Preset | Match ID | Stop Success | Graceful Stop | Cam0 Probe | Cam1 Probe | Cam0 FPS | Cam1 FPS | CPU Avg |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: |
| `fast` | `issue34_fast_1770848727` | true | true | true | true | 30.01 | 30.05 | 39.07% |
| `balanced` | `issue34_balanced_1770848805` | true | true | true | true | 29.64 | 29.55 | 57.65% |
| `high` | `issue34_high_1770848661` | true | true | true | true | 29.70 | 29.73 | 67.20% |

This replaced the previously unstable behavior where `balanced` could produce
unprobeable output and ~10 fps under stress.

### Quality-Per-CPU Ladder Guardrails (Issue #39)

The preset ladder is intentionally shaped for predictable quality/cost tradeoff:

- `fast`: lowest encoder cost (`ultrafast`, `bframes=0`, 20 Mbps)
- `balanced`: moderate cost (`superfast`, `bframes=1`, 22 Mbps)
- `high`: highest quality target in this stable family (`superfast`, `bframes=1`, 25 Mbps)

Operational guardrail: every ladder change must be hardware-validated on metcam with
all of the following:

1. Probeable output on both cameras.
2. Graceful stop on both cameras.
3. Effective fps near target for each preset.
4. CPU usage consistent with preset intent (`fast` <= `balanced` <= `high` in sampled runs).

### GOP Tuning Validation (Issue #40, 2026-02-11)

Real-device A/B runs on metcam (dual-camera, 30s recording, same workflow) were used
to evaluate longer GOP settings for CPU reduction.

| fast preset `key-int-max` | CPU avg | CPU p95 | Cam0 fps | Cam1 fps | Keyframes | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 90 (baseline) | 70.49% | 93.40% | 30.00 | 29.95 | 9 / 9 | Stable stop/finalization |
| 120 | 70.95% / 70.82% | 93.77% / 93.70% | 30.00 / 29.91 | 29.98 / 29.99 | 7 / 7 | No CPU win vs baseline |
| 180 | 77.28% | 95.68% | 30.00 | 29.98 | 4 / 5 | Regression; cam1 segment duration overshot to ~34.29s |

Conclusion: keep `fast` preset at `key-int-max=90` as the validated baseline for
stability and CPU behavior on current hardware/software.

### NV12-to-I420 Handoff Validation (Issue #37, 2026-02-11)

An explicit NV12 handoff experiment (`x264enc` fed with NV12 instead of I420) was
tested on metcam and reverted after regression:

- NV12 branch (`PR #45`) fast runs: CPU avg **~91.4%**, **93.0%**, **92.8%**
- Revert branch (`PR #46`) fast run: CPU avg **~85.4%**
- Stop/finalization remained clean after revert

Conclusion: keep recording encoder handoff at **I420** in baseline. Re-evaluate only
with a different end-to-end pipeline strategy and fresh hardware-in-loop evidence.

### Queue Policy Validation (Issue #33, 2026-02-11)

A stage-specific queue policy experiment was run on metcam under stressed
`balanced` preset conditions:

- Baseline (all three queues `leaky=downstream`), match `issue33_baseline_balanced_1770847733`
  - CPU avg **89.78%**
  - `cam0` output unprobeable (`moov atom not found`)
  - `cam1` effective fps **~10.32**
  - stop result: `cam0` EOS timeout / non-finalized
- Candidate (only `preenc_queue` leaky; post-encode/mux non-leaky), match `issue33_candidate_balanced_1770847866`
  - CPU avg **90.14%**
  - `cam0` output unprobeable (`moov atom not found`)
  - `cam1` effective fps **~10.32**
  - stop result: `cam0` EOS timeout / non-finalized

Conclusion: this queue-policy change did not improve integrity or fps on the target
hardware. Keep current queue policy while addressing root-cause overload via preset
tuning (`#34`, `#39`).

### Recording stop behavior (critical)

Recording uses **EOS stop** for clean segment finalization:

- `recording_service._stop_recording_internal()` calls
  `gst_manager.stop_pipeline(... wait_for_eos=True, timeout=5.0)`
- This is intentional for archive integrity and must remain as recording baseline behavior.

## Preview Pipeline Baseline

Defined by `build_preview_pipeline()` in `src/video-pipeline/pipeline_builders.py`.

Per camera flow:

1. `nvarguscamerasrc` (same source/crop/color path)
2. `x264enc` (`ultrafast`, `zerolatency`, 6 Mbps)
3. `h264parse` (`config-interval=1`, byte-stream)
4. `hlssink2` (2s target, playlist/max-files = 8)

### Preview start behavior

- `preview_service.start_preview()` recreates `/dev/shm/hls` each start call.
- Starts cameras individually as `preview_cam0` / `preview_cam1`.
- Starts exposure synchronization service after pipeline start.

### Preview stop behavior (critical fix)

Preview teardown uses **non-EOS stop** to avoid `hlssink2/splitmuxsink` aborts:

- `preview_service.stop_preview()` stops exposure sync first (for full stop)
- Then calls `gst_manager.stop_pipeline(... wait_for_eos=False, timeout=1.0)`
- This avoids observed crashes:
  - `gstsplitmuxsink.c:2691 check_completed_gop assertion failed`
  - process `SIGABRT`/`SIGSEGV` during rapid start/stop

This non-EOS preview stop policy is part of the baseline and should be preserved.

## Control Plane Baseline

## REST endpoints (authoritative)

- `GET /api/v1/status`
- `GET /api/v1/pipeline-state`
- `GET /api/v1/recording`
- `POST /api/v1/recording`
- `DELETE /api/v1/recording?force=true|false`
- `GET /api/v1/preview`
- `POST /api/v1/preview`
- `DELETE /api/v1/preview`
- `POST /api/v1/preview/restart`
- `GET /api/v1/recording-health`

## WebSocket

- Endpoint: `/ws` (proxied by Caddy to API)
- Initial server frame: `hello`
- Health: `ping` / `pong`
- Command pattern: `command` -> `command_ack` -> `command_result`
- Important actions:
  - `start_recording`, `stop_recording`
  - `start_preview`, `stop_preview`
  - `get_recordings`, `get_logs`

## Locking / Mutual Exclusion Baseline

Managed by `pipeline_manager` with state in `/var/lock/footballvision/`.

Expected policy:

- `recording` has priority and acquires lock with `force=True`
- `preview` acquires lock with `force=False`
- recording and preview must never coexist
- stale lock cleanup occurs on startup

Quick check:

```bash
curl -sS http://localhost:8000/api/v1/pipeline-state
```

Expected idle state:

```json
{"mode":"idle","holder":null,"lock_time":null,"can_preview":true,"can_record":true}
```

## Known Failure Signatures

If these appear, baseline is broken or partially deployed:

- `ERROR: ../gst/multifile/gstsplitmuxsink.c:2691: check_completed_gop`
- API exits with `status=6/ABRT` or `status=11/SEGV` during preview stop
- `Got no output stream for fragment '/dev/shm/hls/cam*.ts'` repeatedly
- `/ws` route returns frontend HTML instead of WS upgrade behavior

## Baseline Restore Playbook

Run this sequence on Jetson when recording/preview is unstable after changes.

### 1) Preserve local work and sync code

```bash
cd /home/mislav/footballvision-pro

git stash push -u -m "pre-baseline-restore-$(date +%F-%H%M%S)" || true
git fetch origin
git checkout main
git pull --ff-only origin main
```

For exact known-good code:

```bash
git checkout 6cd65539a4a8e5c3d3eab8d556158b4825ad7d75
```

### 2) Ensure Caddy baseline is applied

```bash
sudo cp /home/mislav/footballvision-pro/deploy/config/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo caddy reload --config /etc/caddy/Caddyfile
```

Must include:

- `handle /ws { reverse_proxy localhost:8000 }`
- `handle /api/* { reverse_proxy localhost:8000 ... }`
- `/ws` declared before catch-all static handler

### 3) Stabilize API service unit (if restart loops exist)

If your host unit has recursive `ExecStartPost` behavior, clear it with an override:

```bash
sudo mkdir -p /etc/systemd/system/footballvision-api-enhanced.service.d
cat <<'EOF2' | sudo tee /etc/systemd/system/footballvision-api-enhanced.service.d/override.conf
[Service]
ExecStartPost=
EOF2

sudo systemctl daemon-reload
```

### 4) Restart API and verify health

```bash
sudo systemctl restart footballvision-api-enhanced
systemctl is-active footballvision-api-enhanced
curl -sS http://localhost:8000/api/v1/health
```

### 5) Deploy frontend bundle

```bash
cd /home/mislav/footballvision-pro/src/platform/web-dashboard
npm ci
npm run build
sudo rsync -a --delete dist/ /var/www/footballvision/
```

### 6) Smoke tests (must pass)

REST preview stress:

```bash
python3 - <<'PY'
import requests, time
base='http://localhost:8000'
for i in range(8):
    a=requests.post(base+'/api/v1/preview', json={}, timeout=8).json()
    time.sleep(0.2)
    b=requests.delete(base+'/api/v1/preview', timeout=10).json()
    print(i+1, a.get('success'), b.get('success'))
    time.sleep(0.2)
print(requests.get(base+'/api/v1/pipeline-state').json())
PY
```

WebSocket command stress:

```bash
python3 - <<'PY'
import asyncio, json, websockets
async def cmd(ws,i,a):
    cid=f'{a}-{i}'
    await ws.send(json.dumps({'v':1,'type':'command','id':cid,'action':a,'params':{}}))
    while True:
        m=json.loads(await ws.recv())
        if m.get('type')=='command_result' and m.get('id')==cid:
            return m.get('success')
async def main():
    async with websockets.connect('ws://localhost/ws', ping_interval=None) as ws:
        await ws.recv()  # hello
        for i in range(1,7):
            print(i, await cmd(ws,i,'start_preview'), await cmd(ws,i,'stop_preview'))
asyncio.run(main())
PY
```

Log check:

```bash
journalctl -u footballvision-api-enhanced -n 100 --no-pager
# ensure no new gstsplitmuxsink check_completed_gop assertions
```

## Baseline Acceptance Criteria

Baseline is considered restored only if all are true:

1. API service is `active` and stable.
2. Rapid preview start/stop (REST and WS) does not crash API.
3. `/api/v1/pipeline-state` returns `mode=idle` after stop cycles.
4. No new `check_completed_gop` assertions appear in recent logs.
5. Recording start/stop still works with EOS-based stop semantics.
