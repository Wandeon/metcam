#!/usr/bin/env python3
"""
Hardware-in-loop recording regression matrix runner.

Runs recording presets sequentially on a live metcam node, captures stop/integrity/fps/cpu
metrics, writes a structured JSON report, and exits non-zero when thresholds fail.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "camera_config.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "recording-regression"
DEFAULT_RESTART_CMD = "sudo systemctl restart footballvision-api-enhanced"
SUPPORTED_PRESETS = ("fast", "balanced", "high")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_avg_frame_rate(raw: str | None) -> float | None:
    if not raw:
        return None
    if raw in ("0/0", "N/A"):
        return None
    if "/" in raw:
        num, den = raw.split("/", 1)
        try:
            num_f = float(num)
            den_f = float(den)
            if den_f == 0:
                return None
            return num_f / den_f
        except ValueError:
            return None
    try:
        return float(raw)
    except ValueError:
        return None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    ordered = sorted(values)
    idx = (len(ordered) - 1) * (p / 100.0)
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    if lo == hi:
        return ordered[lo]
    frac = idx - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


class MatrixRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.api_base = args.api_base_url.rstrip("/")
        self.config_path = Path(args.config_path)
        self.output_dir = Path(args.output_dir)
        self.restart_cmd = args.restart_cmd
        self.original_config: dict[str, Any] | None = None

    def _api_request(self, method: str, route: str, payload: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
        url = f"{self.api_base}{route}"
        body: bytes | None = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(url=url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API {method} {route} failed: HTTP {e.code}: {raw}") from e
        except error.URLError as e:
            raise RuntimeError(f"API {method} {route} failed: {e}") from e

    def _restart_service(self) -> None:
        cmd = self.restart_cmd.strip()
        if not cmd:
            return
        subprocess.run(cmd, shell=True, check=True)

    def _wait_for_health(self, timeout_seconds: float = 40.0) -> None:
        deadline = time.time() + timeout_seconds
        last_err = "unhealthy"
        while time.time() < deadline:
            try:
                health = self._api_request("GET", "/health", timeout=5.0)
                if health.get("status") == "healthy":
                    return
                last_err = str(health)
            except Exception as e:  # pragma: no cover - exercised in real runs
                last_err = str(e)
            time.sleep(1.0)
        raise RuntimeError(f"API did not become healthy within {timeout_seconds}s: {last_err}")

    def _load_config(self) -> dict[str, Any]:
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def _save_config(self, payload: dict[str, Any]) -> None:
        self.config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _set_quality_preset(self, preset: str) -> None:
        cfg = self._load_config()
        cfg["recording_quality"] = preset
        self._save_config(cfg)

    def _collect_cpu_samples(self, duration_seconds: float) -> list[float]:
        samples: list[float] = []
        deadline = time.time() + duration_seconds
        interval = max(0.2, float(self.args.sample_interval_seconds))
        while time.time() < deadline:
            try:
                metrics = self._api_request("GET", "/system-metrics", timeout=5.0)
                cpu = metrics.get("cpu_usage", {}).get("overall")
                if cpu is not None:
                    samples.append(float(cpu))
            except Exception:
                # Keep run going and report sparse samples.
                pass
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            time.sleep(min(interval, remaining))
        return samples

    def _probe_segment(self, path: str) -> dict[str, Any]:
        if not path:
            return {"ok": False, "error": "missing_path"}
        if not os.path.exists(path):
            return {"ok": False, "error": "segment_missing", "path": path}

        cmd = [
            "/usr/bin/ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate,codec_name",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-of",
            "json",
            path,
        ]
        try:
            probe = subprocess.run(cmd, capture_output=True, text=True, timeout=12.0, check=False)
        except Exception as e:
            return {"ok": False, "error": f"ffprobe_exception:{e}", "path": path}
        if probe.returncode != 0:
            return {"ok": False, "error": (probe.stderr or "").strip() or f"ffprobe_exit_{probe.returncode}", "path": path}

        try:
            parsed = json.loads(probe.stdout or "{}")
        except json.JSONDecodeError:
            parsed = {}

        streams = parsed.get("streams") or []
        fmt = parsed.get("format") or {}
        if not streams:
            return {"ok": False, "error": "no_video_stream", "path": path}
        fps = parse_avg_frame_rate(streams[0].get("avg_frame_rate"))
        return {
            "ok": True,
            "path": path,
            "codec_name": streams[0].get("codec_name"),
            "avg_frame_rate_raw": streams[0].get("avg_frame_rate"),
            "fps": fps,
            "duration_seconds": float(fmt.get("duration")) if fmt.get("duration") else None,
            "size_bytes": int(fmt.get("size")) if fmt.get("size") else None,
            "bit_rate": int(fmt.get("bit_rate")) if fmt.get("bit_rate") else None,
        }

    def _stop_any_active_recording(self) -> None:
        try:
            status = self._api_request("GET", "/recording", timeout=5.0)
            if status.get("recording"):
                self._api_request("DELETE", "/recording?force=true", timeout=30.0)
        except Exception:
            pass

    def _run_one_preset(self, preset: str) -> dict[str, Any]:
        match_id = f"regression-{preset}-{int(time.time())}"
        start_time = utc_now_iso()
        failures: list[str] = []

        self._set_quality_preset(preset)
        self._restart_service()
        self._wait_for_health()

        start_resp = self._api_request(
            "POST",
            "/recording",
            payload={"match_id": match_id, "process_after_recording": False, "force": True},
            timeout=20.0,
        )
        if not start_resp.get("success"):
            failures.append(f"start_failed:{start_resp.get('message')}")
            return {
                "preset": preset,
                "match_id": match_id,
                "started_at": start_time,
                "start_response": start_resp,
                "pass": False,
                "failures": failures,
            }

        cpu_samples = self._collect_cpu_samples(float(self.args.duration_seconds))

        stop_resp = self._api_request("DELETE", "/recording?force=true", timeout=40.0)
        integrity = stop_resp.get("integrity") or {}
        if not stop_resp.get("success"):
            failures.append(f"stop_failed:{stop_resp.get('message')}")
        if integrity.get("all_ok") is not True:
            failures.append("integrity_not_all_ok")

        camera_metrics: dict[str, Any] = {}
        for camera_key, details in (stop_resp.get("camera_stop_results") or {}).items():
            if not isinstance(details, dict):
                continue
            probe = self._probe_segment(str(details.get("segment_path") or ""))
            camera_metrics[camera_key] = {
                "stop": details,
                "probe": probe,
            }
            if not probe.get("ok"):
                failures.append(f"{camera_key}_probe_failed:{probe.get('error')}")
                continue
            fps = probe.get("fps")
            if fps is None:
                failures.append(f"{camera_key}_fps_missing")
            elif fps < float(self.args.min_fps):
                failures.append(f"{camera_key}_fps_low:{fps:.3f}<{self.args.min_fps:.3f}")

        cpu_p95 = percentile(cpu_samples, 95.0)
        cpu_avg = (sum(cpu_samples) / len(cpu_samples)) if cpu_samples else None
        if cpu_p95 is not None and cpu_p95 > float(self.args.max_cpu_p95):
            failures.append(f"cpu_p95_high:{cpu_p95:.2f}>{self.args.max_cpu_p95:.2f}")

        return {
            "preset": preset,
            "match_id": match_id,
            "started_at": start_time,
            "ended_at": utc_now_iso(),
            "start_response": start_resp,
            "stop_response": stop_resp,
            "camera_metrics": camera_metrics,
            "cpu_samples": cpu_samples,
            "cpu_summary": {
                "samples": len(cpu_samples),
                "avg": cpu_avg,
                "p95": cpu_p95,
                "max": max(cpu_samples) if cpu_samples else None,
            },
            "pass": not failures,
            "failures": failures,
        }

    def run(self) -> int:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        requested = [item.strip() for item in self.args.presets.split(",") if item.strip()]
        for preset in requested:
            if preset not in SUPPORTED_PRESETS:
                raise ValueError(f"Unsupported preset '{preset}'. Expected one of: {', '.join(SUPPORTED_PRESETS)}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.original_config = self._load_config()
        results: list[dict[str, Any]] = []
        started_at = utc_now_iso()
        hostname = socket.gethostname()

        try:
            self._wait_for_health()
            self._stop_any_active_recording()
            for preset in requested:
                print(f"[matrix] running preset={preset}", flush=True)
                result = self._run_one_preset(preset)
                results.append(result)
                print(f"[matrix] preset={preset} pass={result.get('pass')} failures={result.get('failures')}", flush=True)
        finally:
            if self.original_config is not None:
                self._save_config(self.original_config)
                self._restart_service()
                self._wait_for_health()
            self._stop_any_active_recording()

        passed = sum(1 for item in results if item.get("pass"))
        report = {
            "schema_version": 1,
            "generated_at": utc_now_iso(),
            "started_at": started_at,
            "host": hostname,
            "api_base_url": self.api_base,
            "config_path": str(self.config_path),
            "thresholds": {
                "min_fps": float(self.args.min_fps),
                "max_cpu_p95": float(self.args.max_cpu_p95),
            },
            "presets": requested,
            "results": results,
            "summary": {
                "total": len(results),
                "passed": passed,
                "failed": len(results) - passed,
            },
        }

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = self.output_dir / f"recording-matrix-{stamp}.json"
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"[matrix] report={out_path}", flush=True)

        if report["summary"]["failed"] > 0:
            return 1
        return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run recording preset regression matrix on a live metcam node.")
    parser.add_argument("--api-base-url", default="http://localhost:8000/api/v1")
    parser.add_argument("--config-path", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--restart-cmd", default=DEFAULT_RESTART_CMD)
    parser.add_argument("--presets", default="fast,balanced,high")
    parser.add_argument("--duration-seconds", type=float, default=20.0)
    parser.add_argument("--sample-interval-seconds", type=float, default=1.0)
    parser.add_argument("--min-fps", type=float, default=24.0)
    parser.add_argument("--max-cpu-p95", type=float, default=95.0)
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    runner = MatrixRunner(args)
    try:
        return runner.run()
    except Exception as e:
        print(f"[matrix] fatal: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
