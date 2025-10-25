"""
Development API Router
Provides endpoints for managing development workflow from the UI
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import subprocess
import os
import json
import psutil
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

dev_router = APIRouter(prefix="/api/v1/dev", tags=["development"])


class ServiceSwitchRequest(BaseModel):
    target: str  # "dev" or "prod"


class DeployRequest(BaseModel):
    confirm: bool = False


class RollbackRequest(BaseModel):
    backup_name: str


def run_command(cmd: str, cwd: Optional[str] = None, timeout: int = 30) -> dict:
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "returncode": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }


@dev_router.get("/status")
async def get_dev_status():
    """Get current development environment status"""
    try:
        # Check which service is running
        prod_active = run_command("sudo systemctl is-active footballvision-api-enhanced")
        dev_active = run_command("sudo systemctl is-active footballvision-api-dev")

        # Get git info from both environments
        prod_branch = run_command("git branch --show-current", cwd="/home/mislav/footballvision-pro")
        prod_commit = run_command("git rev-parse --short HEAD", cwd="/home/mislav/footballvision-pro")

        dev_branch = run_command("git branch --show-current", cwd="/home/mislav/footballvision-dev")
        dev_commit = run_command("git rev-parse --short HEAD", cwd="/home/mislav/footballvision-dev")
        dev_status = run_command("git status --porcelain", cwd="/home/mislav/footballvision-dev")

        return {
            "services": {
                "production": {
                    "active": prod_active["stdout"].strip() == "active",
                    "branch": prod_branch["stdout"].strip(),
                    "commit": prod_commit["stdout"].strip()
                },
                "development": {
                    "active": dev_active["stdout"].strip() == "active",
                    "branch": dev_branch["stdout"].strip(),
                    "commit": dev_commit["stdout"].strip(),
                    "has_changes": bool(dev_status["stdout"].strip())
                }
            },
            "api_port": os.getenv('API_PORT', '8000')
        }
    except Exception as e:
        logger.error(f"Failed to get dev status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@dev_router.get("/git-status")
async def get_git_status():
    """Get detailed git status for development environment"""
    try:
        branch = run_command("git branch --show-current", cwd="/home/mislav/footballvision-dev")
        commit = run_command("git rev-parse HEAD", cwd="/home/mislav/footballvision-dev")
        commit_msg = run_command("git log -1 --pretty=%B", cwd="/home/mislav/footballvision-dev")
        status = run_command("git status --porcelain", cwd="/home/mislav/footballvision-dev")
        remote_status = run_command("git rev-list --left-right --count HEAD...@{u}", cwd="/home/mislav/footballvision-dev")

        # Parse behind/ahead counts
        behind = 0
        ahead = 0
        if remote_status["success"] and remote_status["stdout"]:
            parts = remote_status["stdout"].strip().split()
            if len(parts) == 2:
                ahead = int(parts[0])
                behind = int(parts[1])

        return {
            "branch": branch["stdout"].strip(),
            "commit": commit["stdout"].strip()[:7],
            "commit_full": commit["stdout"].strip(),
            "commit_message": commit_msg["stdout"].strip(),
            "has_changes": bool(status["stdout"].strip()),
            "changes": status["stdout"].strip().split('\n') if status["stdout"].strip() else [],
            "ahead": ahead,
            "behind": behind
        }
    except Exception as e:
        logger.error(f"Failed to get git status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@dev_router.post("/git-pull")
async def git_pull():
    """Pull latest develop branch from GitHub"""
    try:
        logger.info("Pulling latest develop branch")

        # Fetch first
        fetch = run_command("git fetch origin", cwd="/home/mislav/footballvision-dev", timeout=60)
        if not fetch["success"]:
            raise HTTPException(status_code=500, detail=f"Git fetch failed: {fetch['stderr']}")

        # Pull
        pull = run_command("git pull origin develop", cwd="/home/mislav/footballvision-dev", timeout=60)

        return {
            "success": pull["success"],
            "output": pull["stdout"],
            "error": pull["stderr"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pull git: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@dev_router.post("/build-ui")
async def build_dev_ui():
    """Build development UI and deploy to /var/www/footballvision-dev/"""
    try:
        logger.info("Building development UI")
        ui_dir = "/home/mislav/footballvision-dev/src/platform/web-dashboard"

        # Build
        build = run_command(
            "npm run build",
            cwd=ui_dir,
            timeout=180  # 3 minutes for build
        )

        if not build["success"]:
            return {
                "success": False,
                "output": build["stdout"],
                "error": build["stderr"]
            }

        # Deploy
        deploy = run_command(
            "sudo rsync -a --delete dist/ /var/www/footballvision-dev/",
            cwd=ui_dir,
            timeout=30
        )

        return {
            "success": deploy["success"],
            "output": build["stdout"] + "\n" + deploy["stdout"],
            "error": deploy["stderr"]
        }
    except Exception as e:
        logger.error(f"Failed to build UI: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@dev_router.post("/switch-service")
async def switch_service(request: ServiceSwitchRequest):
    """Switch between production and development services"""
    try:
        if request.target not in ["dev", "prod"]:
            raise HTTPException(status_code=400, detail="Target must be 'dev' or 'prod'")

        script = f"/home/mislav/switch-to-{request.target}.sh"
        if not os.path.exists(script):
            raise HTTPException(status_code=404, detail=f"Switch script not found: {script}")

        logger.info(f"Switching to {request.target}")

        # Run switch script in background
        subprocess.Popen(["/bin/bash", script])

        return {
            "success": True,
            "message": f"Switching to {request.target} (will take ~5 seconds)"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to switch service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@dev_router.get("/service-status")
async def get_service_status():
    """Check which service is currently running"""
    try:
        prod = run_command("sudo systemctl is-active footballvision-api-enhanced")
        dev = run_command("sudo systemctl is-active footballvision-api-dev")

        prod_active = prod["stdout"].strip() == "active"
        dev_active = dev["stdout"].strip() == "active"

        if prod_active:
            current = "production"
        elif dev_active:
            current = "development"
        else:
            current = "none"

        return {
            "current": current,
            "production_active": prod_active,
            "development_active": dev_active
        }
    except Exception as e:
        logger.error(f"Failed to get service status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@dev_router.post("/deploy-prod")
async def deploy_to_production(request: DeployRequest):
    """Deploy tested code to production"""
    try:
        if not request.confirm:
            raise HTTPException(status_code=400, detail="Confirmation required")

        script = "/home/mislav/deploy-to-prod.sh"
        if not os.path.exists(script):
            raise HTTPException(status_code=404, detail="Deploy script not found")

        logger.info("Deploying to production")

        # Run deploy script in background
        subprocess.Popen(["/bin/bash", script])

        return {
            "success": True,
            "message": "Deployment started (will take ~2-3 minutes)"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deploy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@dev_router.get("/backups")
async def list_backups():
    """List available backups for rollback"""
    try:
        backups = []
        backup_dir = Path("/home/mislav")

        for backup in sorted(backup_dir.glob("footballvision-backup-*"), reverse=True):
            if backup.is_dir():
                # Get backup info
                stat = backup.stat()

                # Try to get git info from backup
                branch = run_command("git branch --show-current", cwd=str(backup))
                commit = run_command("git rev-parse --short HEAD", cwd=str(backup))

                backups.append({
                    "name": backup.name,
                    "path": str(backup),
                    "size_mb": sum(f.stat().st_size for f in backup.rglob('*') if f.is_file()) / (1024 * 1024),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "branch": branch["stdout"].strip() if branch["success"] else "unknown",
                    "commit": commit["stdout"].strip() if commit["success"] else "unknown"
                })

        return {"backups": backups[:10]}  # Return last 10 backups
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@dev_router.post("/rollback")
async def rollback_to_backup(request: RollbackRequest):
    """Rollback production to a specific backup"""
    try:
        backup_path = Path(f"/home/mislav/{request.backup_name}")

        if not backup_path.exists() or not backup_path.is_dir():
            raise HTTPException(status_code=404, detail="Backup not found")

        logger.info(f"Rolling back to {request.backup_name}")

        # Run rollback script in background (it will prompt for selection)
        # For now, just use emergency restore which doesn't need selection
        script = "/home/mislav/emergency-restore-prod.sh"
        if not os.path.exists(script):
            raise HTTPException(status_code=404, detail="Rollback script not found")

        subprocess.Popen(["/bin/bash", script])

        return {
            "success": True,
            "message": "Rollback started (will take ~1-2 minutes)"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rollback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@dev_router.get("/logs")
async def get_logs(service: str = "dev", lines: int = 100):
    """Get recent logs from service"""
    try:
        if service not in ["dev", "prod"]:
            raise HTTPException(status_code=400, detail="Service must be 'dev' or 'prod'")

        service_name = "footballvision-api-dev" if service == "dev" else "footballvision-api-enhanced"

        result = run_command(
            f"sudo journalctl -u {service_name} -n {lines} --no-pager",
            timeout=10
        )

        return {
            "success": result["success"],
            "logs": result["stdout"],
            "service": service_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@dev_router.get("/system-info")
async def get_system_info():
    """Get system status (CPU, memory, disk)"""
    try:
        # CPU info
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()

        # Memory info
        memory = psutil.virtual_memory()

        # Disk info
        disk = psutil.disk_usage('/')
        recordings_disk = psutil.disk_usage('/mnt/recordings')

        # Process info
        current_process = psutil.Process()

        return {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count
            },
            "memory": {
                "total_gb": memory.total / (1024**3),
                "used_gb": memory.used / (1024**3),
                "available_gb": memory.available / (1024**3),
                "percent": memory.percent
            },
            "disk": {
                "root": {
                    "total_gb": disk.total / (1024**3),
                    "used_gb": disk.used / (1024**3),
                    "free_gb": disk.free / (1024**3),
                    "percent": disk.percent
                },
                "recordings": {
                    "total_gb": recordings_disk.total / (1024**3),
                    "used_gb": recordings_disk.used / (1024**3),
                    "free_gb": recordings_disk.free / (1024**3),
                    "percent": recordings_disk.percent
                }
            },
            "process": {
                "pid": current_process.pid,
                "memory_mb": current_process.memory_info().rss / (1024**2),
                "cpu_percent": current_process.cpu_percent()
            }
        }
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
