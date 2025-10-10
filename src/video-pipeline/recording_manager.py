#!/usr/bin/env python3
"""FootballVision Pro - Recording Manager

Authoritative controller that wraps the on-device dual-camera recording script.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional


class RecordingManager:
    """Control the dual-camera recording workflow via the production shell script."""

    def __init__(
        self,
        output_root: str = "/mnt/recordings",
        script_path: Optional[Path] = None,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self.script_path = Path(script_path) if script_path else repo_root / "scripts" / "record_dual_1080p30.sh"
        self.output_root = Path(output_root)

        self.output_root.mkdir(parents=True, exist_ok=True)

        self.process: Optional[subprocess.Popen] = None
        self.match_id: Optional[str] = None
        self.start_time: Optional[datetime] = None
        self.pid_file = Path("/tmp/recording.pid")
        self.match_id_file = Path("/tmp/recording_match_id.txt")
        self.manifest_filename = "upload_manifest.json"
        self.upload_delay_minutes = 10

        if not self.script_path.exists():
            raise FileNotFoundError(f"Recording script not found: {self.script_path}")

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def start_recording(self, match_id: Optional[str] = None, **_: int) -> Dict[str, object]:
        """Start recording using the authoritative shell script."""
        if self.is_recording():
            raise RuntimeError("Recording already in progress")

        if not match_id:
            match_id = f"match_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.match_id = match_id
        self.start_time = datetime.utcnow()
        self.process = subprocess.Popen([str(self.script_path), match_id])

        # Persist PID and match ID for external tooling parity with the field device
        self.pid_file.write_text(str(self.process.pid))
        self.match_id_file.write_text(match_id)

        # Give the script a moment to boot pipelines so we can report status
        time.sleep(3)
        if self.process.poll() is not None:
            raise RuntimeError("Recording script exited before pipelines initialised")

        return {
            "status": "recording",
            "recording": True,
            "match_id": match_id,
            "pid": self.process.pid,
        }

    def stop_recording(self) -> Dict[str, object]:
        if not self.pid_file.exists():
            return {"status": "idle", "recording": False}

        pid = int(self.pid_file.read_text().strip())
        match_id = self.match_id or (self.match_id_file.read_text().strip() if self.match_id_file.exists() else None)

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

        time.sleep(10)

        self.pid_file.unlink(missing_ok=True)
        self.match_id_file.unlink(missing_ok=True)

        stop_time = datetime.utcnow()
        upload_ready_time = stop_time + timedelta(minutes=self.upload_delay_minutes)

        segments_dir = self.output_root / (match_id or "unknown") / "segments"
        cam0_segments = sorted(segments_dir.glob("cam0_*.mp4")) if segments_dir.exists() else []
        cam1_segments = sorted(segments_dir.glob("cam1_*.mp4")) if segments_dir.exists() else []
        total_size_mb = sum(s.stat().st_size for s in cam0_segments + cam1_segments) / 1024 / 1024 if cam0_segments or cam1_segments else 0.0

        if match_id:
            self._write_upload_manifest(match_id, segments_dir, stop_time, upload_ready_time)

        duration = (stop_time - self.start_time).total_seconds() if self.start_time else 0.0

        self.process = None
        self.match_id = None
        self.start_time = None

        return {
            "status": "stopped",
            "recording": False,
            "match_id": match_id,
            "duration_seconds": duration,
            "upload_ready_at": upload_ready_time.isoformat() + "Z",
            "segments": {
                "cam0_count": len(cam0_segments),
                "cam1_count": len(cam1_segments),
                "total_size_mb": total_size_mb,
                "segments_dir": str(segments_dir),
            },
        }

    def get_status(self) -> Dict[str, object]:
        if self.is_recording():
            match_id = self.match_id
            if not match_id and self.match_id_file.exists():
                match_id = self.match_id_file.read_text().strip()
            return {
                "status": "recording",
                "recording": True,
                "match_id": match_id,
                "started_at": self.start_time.isoformat() + "Z" if self.start_time else None,
            }
        return {"status": "idle", "recording": False}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def is_recording(self) -> bool:
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text().strip())
                os.kill(pid, 0)
                return True
            except (OSError, ValueError):
                self.pid_file.unlink(missing_ok=True)
                self.match_id_file.unlink(missing_ok=True)
        return False

    def _write_upload_manifest(
        self,
        match_id: str,
        segments_dir: Path,
        stop_time: datetime,
        upload_ready_time: datetime,
    ) -> None:
        match_dir = self.output_root / match_id
        match_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = match_dir / self.manifest_filename
        tmp_path = manifest_path.with_suffix('.tmp')
        manifest = {
            "match_id": match_id,
            "stopped_at": stop_time.isoformat() + "Z",
            "upload_ready_at": upload_ready_time.isoformat() + "Z",
            "upload_delay_minutes": self.upload_delay_minutes,
            "segments_dir": str(segments_dir),
        }

        tmp_path.write_text(json.dumps(manifest, indent=2))
        os.replace(tmp_path, manifest_path)


if __name__ == "__main__":
    controller = RecordingManager()
    status = controller.start_recording()
    print(json.dumps(status, indent=2))
    time.sleep(5)
    print(json.dumps(controller.stop_recording(), indent=2))
