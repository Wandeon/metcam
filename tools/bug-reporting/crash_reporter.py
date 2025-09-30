#!/usr/bin/env python3
"""
Automated Crash Reporter for FootballVision Pro
Collects system state and logs when crashes occur
"""

import os
import sys
import json
import subprocess
import datetime
from pathlib import Path
from typing import Dict, Any


class CrashReporter:
    """Automated crash report generator"""

    def __init__(self, crash_data: Dict[str, Any] = None):
        self.crash_data = crash_data or {}
        self.report = {}
        self.report_dir = Path("/var/log/footballvision/crashes")
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def collect_system_info(self) -> Dict[str, Any]:
        """Collect system information"""
        info = {
            "timestamp": datetime.datetime.now().isoformat(),
            "hostname": subprocess.getoutput("hostname"),
            "uptime": subprocess.getoutput("uptime -p"),
            "kernel": subprocess.getoutput("uname -r"),
        }

        # Jetson info
        try:
            with open("/etc/nv_tegra_release") as f:
                info["jetson_release"] = f.read().strip()
        except:
            info["jetson_release"] = "Unknown"

        # Memory
        mem_info = subprocess.getoutput("free -h")
        info["memory"] = mem_info

        # Storage
        storage_info = subprocess.getoutput("df -h /")
        info["storage"] = storage_info

        # Temperature
        try:
            with open("/sys/devices/virtual/thermal/thermal_zone0/temp") as f:
                temp = int(f.read().strip()) / 1000
                info["temperature_c"] = temp
        except:
            info["temperature_c"] = "Unknown"

        return info

    def collect_logs(self) -> Dict[str, str]:
        """Collect relevant logs"""
        logs = {}

        # System logs
        logs["systemd"] = subprocess.getoutput(
            "journalctl -u footballvision.service -n 100 --no-pager"
        )

        # Application logs
        log_file = Path("/var/log/footballvision/app.log")
        if log_file.exists():
            logs["application"] = log_file.read_text()[-10000:]  # Last 10KB

        # Kernel logs
        logs["dmesg"] = subprocess.getoutput("dmesg | tail -100")

        return logs

    def collect_crash_dump(self) -> Dict[str, Any]:
        """Collect crash-specific information"""
        dump = {
            "exception": self.crash_data.get("exception", "Unknown"),
            "traceback": self.crash_data.get("traceback", ""),
            "process_id": os.getpid(),
            "working_directory": os.getcwd(),
        }

        # Environment variables (filtered)
        safe_env = {
            k: v for k, v in os.environ.items()
            if not any(secret in k.lower() for secret in ["key", "password", "token", "secret"])
        }
        dump["environment"] = safe_env

        return dump

    def generate_report(self) -> Dict[str, Any]:
        """Generate complete crash report"""
        self.report = {
            "crash_id": f"CRASH-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "system_info": self.collect_system_info(),
            "crash_dump": self.collect_crash_dump(),
            "logs": self.collect_logs(),
        }
        return self.report

    def save_report(self) -> Path:
        """Save report to disk"""
        report_file = self.report_dir / f"{self.report['crash_id']}.json"
        with open(report_file, 'w') as f:
            json.dump(self.report, f, indent=2)
        print(f"Crash report saved: {report_file}")
        return report_file

    def send_report(self, report_file: Path) -> bool:
        """Send report to support (placeholder)"""
        # TODO: Implement report upload to support server
        print(f"Report ready for upload: {report_file}")
        print("Please send this report to: support@footballvision.com")
        return True


def handle_crash(exception: Exception):
    """Main crash handler"""
    import traceback

    crash_data = {
        "exception": str(exception),
        "traceback": traceback.format_exc(),
    }

    reporter = CrashReporter(crash_data)
    reporter.generate_report()
    report_file = reporter.save_report()
    reporter.send_report(report_file)


if __name__ == "__main__":
    # Test crash reporter
    try:
        # Simulate crash
        raise RuntimeError("Test crash for reporting system")
    except Exception as e:
        handle_crash(e)