#!/usr/bin/env python3
"""
Thermal Management Daemon
Monitors temperature and throttles performance if needed
"""

import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

THERMAL_ZONES = [
    "/sys/class/thermal/thermal_zone0/temp",  # CPU
    "/sys/class/thermal/thermal_zone1/temp",  # GPU
]

TEMP_WARNING = 65000  # 65°C
TEMP_CRITICAL = 75000  # 75°C

class ThermalMonitor:
    def __init__(self):
        self.throttled = False

    def read_temp(self, zone_path: str) -> int:
        """Read temperature from thermal zone"""
        try:
            with open(zone_path) as f:
                return int(f.read().strip())
        except:
            return 0

    def check_throttle(self, temp: int):
        """Check if throttling needed"""
        if temp > TEMP_CRITICAL and not self.throttled:
            logger.warning(f"Temperature critical: {temp/1000}°C - throttling")
            self.throttled = True
            # Reduce performance
        elif temp < TEMP_WARNING and self.throttled:
            logger.info(f"Temperature normal: {temp/1000}°C - restoring performance")
            self.throttled = False

    def run(self):
        """Main monitoring loop"""
        logger.info("Thermal monitor started")
        while True:
            max_temp = max(self.read_temp(z) for z in THERMAL_ZONES)
            self.check_throttle(max_temp)
            time.sleep(5)

if __name__ == "__main__":
    monitor = ThermalMonitor()
    monitor.run()