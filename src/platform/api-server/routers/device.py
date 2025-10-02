"""
W36: Device Management
Remote configuration and OTA updates
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
import subprocess

router = APIRouter(prefix="/api/v1/device", tags=["Device Management"])

class DeviceInfo(BaseModel):
    device_id: str
    hostname: str
    version: str
    platform: str
    uptime_seconds: int
    cameras_detected: int

class OTAUpdate(BaseModel):
    version: str
    url: Optional[str] = None
    force: bool = False

class ConfigUpdate(BaseModel):
    key: str
    value: str

@router.get("/info", response_model=DeviceInfo)
async def get_device_info():
    """
    Get device information

    Returns:
        Device details including version, platform, uptime
    """
    import socket
    import os

    # Get uptime
    try:
        with open('/proc/uptime', 'r') as f:
            uptime = int(float(f.readline().split()[0]))
    except:
        uptime = 0

    # Count cameras
    try:
        cameras = len([f for f in os.listdir('/dev') if f.startswith('video')])
    except:
        cameras = 0

    return DeviceInfo(
        device_id="jetson-001",  # TODO: Get from persistent storage
        hostname=socket.gethostname(),
        version="1.0.0",  # TODO: Get from version file
        platform="Jetson Orin Nano",
        uptime_seconds=uptime,
        cameras_detected=cameras
    )

@router.post("/update")
async def ota_update(update: OTAUpdate):
    """
    Trigger OTA (Over-The-Air) firmware update

    Args:
        update: Update configuration with version and URL

    Returns:
        Update status
    """
    # TODO: Implement OTA update logic
    # 1. Download update package from URL
    # 2. Verify signature
    # 3. Apply update
    # 4. Schedule reboot

    return {
        "status": "update_scheduled",
        "version": update.version,
        "message": f"OTA update to version {update.version} scheduled",
        "reboot_required": True
    }

@router.get("/config")
async def get_config():
    """
    Get device configuration

    Returns:
        Current device configuration
    """
    # TODO: Load from configuration file
    return {
        "device_id": "jetson-001",
        "recording_path": "/mnt/recordings",
        "resolution": "4032x3040",
        "framerate": 30,
        "bitrate": "100Mbps",
        "upload_enabled": False,
        "upload_bandwidth_limit_mbps": 300
    }

@router.put("/config")
async def update_config(config: Dict[str, any]):
    """
    Update device configuration

    Args:
        config: Configuration key-value pairs

    Returns:
        Updated configuration
    """
    # TODO: Validate and save configuration
    # TODO: Apply configuration changes (may require service restart)

    return {
        "status": "success",
        "message": "Configuration updated",
        "config": config,
        "restart_required": True
    }

@router.post("/reboot")
async def reboot_device(delay_seconds: int = 10):
    """
    Reboot device

    Args:
        delay_seconds: Delay before reboot (default: 10)

    Returns:
        Reboot confirmation
    """
    # TODO: Schedule reboot
    # subprocess.run(['sudo', 'shutdown', '-r', f'+{delay_seconds//60}'])

    return {
        "status": "reboot_scheduled",
        "delay_seconds": delay_seconds,
        "message": f"Device will reboot in {delay_seconds} seconds"
    }

@router.get("/logs")
async def get_logs(lines: int = 100, service: Optional[str] = None):
    """
    Get system logs

    Args:
        lines: Number of log lines to return
        service: Filter by service name

    Returns:
        Log entries
    """
    try:
        if service:
            cmd = ['journalctl', '-u', service, '-n', str(lines), '--no-pager']
        else:
            cmd = ['journalctl', '-n', str(lines), '--no-pager']

        result = subprocess.run(cmd, capture_output=True, text=True)

        return {
            "service": service or "system",
            "lines": lines,
            "logs": result.stdout.split('\n')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
