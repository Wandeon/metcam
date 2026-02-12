#!/usr/bin/env bash
# Deterministic production deploy with config preservation, rollback, and health/smoke checks.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

BRANCH="main"
API_URL="http://localhost:8000/api/v1"
SERVICE_NAME="footballvision-api-enhanced"
CONFIG_REL_PATH="config/camera_config.json"
SMOKE_DURATION_SECONDS=12
RUN_SMOKE=1
DEPLOY_CADDY=1
DEPLOY_SYSTEMD=1
DEPLOY_FRONTEND=1
FORCE_FRONTEND=0

FRONTEND_REL_DIR="src/platform/web-dashboard"
FRONTEND_DEPLOY_DIR="/var/www/footballvision"

PRE_DEPLOY_COMMIT=""
TMP_DIR=""
CONFIG_BACKUP=""
FRONTEND_BACKUP_DIR=""
ROLLBACK_IN_PROGRESS=0

usage() {
    cat <<'EOF'
Usage: ./deploy/deploy-safe.sh [options]

Options:
  --branch <name>             Git branch to deploy (default: main)
  --api-url <url>             API base URL (default: http://localhost:8000/api/v1)
  --smoke-duration <seconds>  Recording smoke duration (default: 12)
  --no-smoke                  Skip recording smoke check
  --skip-caddy                Do not deploy/reload Caddy config
  --skip-systemd              Do not deploy/reload systemd service file
  --skip-frontend             Do not build/deploy the web dashboard
  --force-frontend            Force rebuild/redeploy of the web dashboard
  -h, --help                  Show this help
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --branch)
                BRANCH="$2"
                shift 2
                ;;
            --api-url)
                API_URL="$2"
                shift 2
                ;;
            --smoke-duration)
                SMOKE_DURATION_SECONDS="$2"
                shift 2
                ;;
            --no-smoke)
                RUN_SMOKE=0
                shift
                ;;
            --skip-caddy)
                DEPLOY_CADDY=0
                shift
                ;;
            --skip-systemd)
                DEPLOY_SYSTEMD=0
                shift
                ;;
            --skip-frontend)
                DEPLOY_FRONTEND=0
                shift
                ;;
            --force-frontend)
                FORCE_FRONTEND=1
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 2
                ;;
        esac
    done
}

require_clean_tree_except_config() {
    local dirty
    dirty="$(git -C "$REPO_DIR" status --porcelain --untracked-files=no || true)"
    dirty="$(echo "$dirty" | grep -v " $CONFIG_REL_PATH$" || true)"
    if [[ -n "${dirty}" ]]; then
        log_error "Working tree has non-config changes. Refusing deploy."
        echo "$dirty"
        exit 2
    fi
}

backup_config() {
    TMP_DIR="$(mktemp -d /tmp/fv-deploy-safe.XXXXXX)"
    CONFIG_BACKUP="$TMP_DIR/camera_config.json"
    if [[ -f "$REPO_DIR/$CONFIG_REL_PATH" ]]; then
        cp "$REPO_DIR/$CONFIG_REL_PATH" "$CONFIG_BACKUP"
        log_info "Backed up local config to $CONFIG_BACKUP"
    else
        log_warn "Config file not found at $REPO_DIR/$CONFIG_REL_PATH"
    fi
}

restore_config() {
    if [[ -n "$CONFIG_BACKUP" && -f "$CONFIG_BACKUP" ]]; then
        cp "$CONFIG_BACKUP" "$REPO_DIR/$CONFIG_REL_PATH"
        log_info "Restored preserved config to $CONFIG_REL_PATH"
    fi
}

backup_frontend() {
    if [[ "$DEPLOY_FRONTEND" -ne 1 ]]; then
        return 0
    fi
    if [[ -n "$FRONTEND_BACKUP_DIR" ]]; then
        return 0
    fi
    FRONTEND_BACKUP_DIR="$TMP_DIR/frontend_backup"
    mkdir -p "$FRONTEND_BACKUP_DIR"
    if [[ -d "$FRONTEND_DEPLOY_DIR" ]]; then
        rsync -a --delete "$FRONTEND_DEPLOY_DIR/" "$FRONTEND_BACKUP_DIR/" || true
        log_info "Backed up frontend to $FRONTEND_BACKUP_DIR"
    else
        log_warn "Frontend deploy dir not found at $FRONTEND_DEPLOY_DIR (skipping backup)"
    fi
}

restore_frontend() {
    if [[ "$DEPLOY_FRONTEND" -ne 1 ]]; then
        return 0
    fi
    if [[ -z "$FRONTEND_BACKUP_DIR" || ! -d "$FRONTEND_BACKUP_DIR" ]]; then
        return 0
    fi
    sudo mkdir -p "$FRONTEND_DEPLOY_DIR"
    sudo rsync -a --delete "$FRONTEND_BACKUP_DIR/" "$FRONTEND_DEPLOY_DIR/" || true
    log_info "Restored frontend to $FRONTEND_DEPLOY_DIR"
}

frontend_should_deploy() {
    if [[ "$DEPLOY_FRONTEND" -ne 1 ]]; then
        return 1
    fi
    if [[ "$FORCE_FRONTEND" -eq 1 ]]; then
        return 0
    fi
    local changed
    changed="$(git -C "$REPO_DIR" diff --name-only "$PRE_DEPLOY_COMMIT"..HEAD 2>/dev/null || true)"
    if echo "$changed" | grep -q "^${FRONTEND_REL_DIR}/"; then
        return 0
    fi
    return 1
}

deploy_frontend() {
    if ! frontend_should_deploy; then
        log_info "Frontend unchanged; skipping web dashboard deploy"
        return 0
    fi

    local ui_dir="$REPO_DIR/$FRONTEND_REL_DIR"
    if [[ ! -d "$ui_dir" ]]; then
        log_warn "Frontend directory not found at $ui_dir; skipping"
        return 0
    fi

    backup_frontend

    log_info "Building and deploying web dashboard"
    pushd "$ui_dir" >/dev/null
    if [[ -f package-lock.json ]]; then
        npm ci
    else
        npm install
    fi
    npm run build
    popd >/dev/null

    sudo mkdir -p "$FRONTEND_DEPLOY_DIR"
    sudo rsync -a --delete "$ui_dir/dist/" "$FRONTEND_DEPLOY_DIR/"
    log_success "Web dashboard deployed to $FRONTEND_DEPLOY_DIR"
}

wait_for_health() {
    local timeout_seconds="${1:-40}"
    local deadline=$((SECONDS + timeout_seconds))
    while (( SECONDS < deadline )); do
        if curl -fsS "$API_URL/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

stop_any_active_recording() {
    local rec
    rec="$(curl -fsS "$API_URL/recording" 2>/dev/null || true)"
    if [[ -z "$rec" ]]; then
        return 0
    fi
    python3 - <<'PY' "$rec"
import json
import sys
raw = sys.argv[1]
try:
    payload = json.loads(raw)
except Exception:
    raise SystemExit(0)
if payload.get("recording"):
    raise SystemExit(1)
raise SystemExit(0)
PY
    local has_active=$?
    if [[ "$has_active" -eq 1 ]]; then
        log_warn "Active recording detected, forcing stop"
        curl -fsS -X DELETE "$API_URL/recording?force=true" >/dev/null || true
    fi
}

deploy_runtime_files() {
    if [[ "$DEPLOY_SYSTEMD" -eq 1 ]]; then
        sudo cp "$REPO_DIR/deploy/systemd/footballvision-api-enhanced.service" "/etc/systemd/system/footballvision-api-enhanced.service"
        sudo systemctl daemon-reload
    fi
    if [[ "$DEPLOY_CADDY" -eq 1 ]]; then
        sudo cp "$REPO_DIR/deploy/config/Caddyfile" /etc/caddy/Caddyfile
        sudo caddy validate --config /etc/caddy/Caddyfile
        sudo caddy reload --config /etc/caddy/Caddyfile
    fi
}

restart_api_service() {
    sudo systemctl reset-failed "$SERVICE_NAME" || true
    sudo systemctl restart "$SERVICE_NAME"
    if ! wait_for_health 45; then
        log_error "API health check failed after restart"
        return 1
    fi
    log_success "API health endpoint is reachable"
}

run_recording_smoke() {
    local match_id="deploy_smoke_$(date +%Y%m%d_%H%M%S)"
    log_info "Running recording smoke check (match_id=$match_id, duration=${SMOKE_DURATION_SECONDS}s)"

    local start_resp
    start_resp="$(curl -fsS -X POST "$API_URL/recording" \
        -H 'Content-Type: application/json' \
        -d "{\"match_id\":\"${match_id}\",\"force\":true,\"process_after_recording\":false}")"

    python3 - <<'PY' "$start_resp"
import json
import sys
payload = json.loads(sys.argv[1])
if not payload.get("success"):
    raise SystemExit(f"start failed: {payload.get('message')}")
PY

    sleep "$SMOKE_DURATION_SECONDS"

    local stop_resp
    stop_resp="$(curl -fsS -X DELETE "$API_URL/recording?force=true")"
    local status_after
    status_after="$(curl -fsS "$API_URL/recording")"

    python3 - <<'PY' "$stop_resp" "$status_after"
import json
import sys
stop = json.loads(sys.argv[1])
status = json.loads(sys.argv[2])
issues = []
if not stop.get("transport_success"):
    issues.append(f"transport_success=false ({stop.get('message')})")
integrity = stop.get("integrity") or {}
if integrity.get("all_ok") is not True:
    issues.append(f"integrity_not_all_ok ({integrity.get('all_ok')})")
if status.get("recording"):
    issues.append("recording_still_active_after_stop")
if issues:
    raise SystemExit("; ".join(issues))
PY

    log_success "Recording smoke check passed"
}

rollback() {
    if [[ "$ROLLBACK_IN_PROGRESS" -eq 1 ]]; then
        return 0
    fi
    ROLLBACK_IN_PROGRESS=1
    set +e
    log_error "Deploy failed; rolling back to commit $PRE_DEPLOY_COMMIT"

    cd "$REPO_DIR"
    stop_any_active_recording
    git fetch origin "$BRANCH" >/dev/null 2>&1 || true
    git checkout "$BRANCH" >/dev/null 2>&1 || true
    git reset --hard "$PRE_DEPLOY_COMMIT" >/dev/null 2>&1 || true
    restore_config
    restore_frontend
    deploy_runtime_files >/dev/null 2>&1 || true
    restart_api_service >/dev/null 2>&1 || true

    if wait_for_health 20; then
        log_warn "Rollback completed and API is healthy"
    else
        log_error "Rollback attempted but API health is still failing"
    fi
}

on_error_trap() {
    local line="$1"
    log_error "Failure at line $line"
    rollback
    exit 1
}

cleanup() {
    if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
        rm -rf "$TMP_DIR"
    fi
}

main() {
    parse_args "$@"

    if [[ "$EUID" -eq 0 ]]; then
        log_error "Run as regular user (script uses sudo where needed)"
        exit 2
    fi

    trap 'on_error_trap $LINENO' ERR
    trap cleanup EXIT

    cd "$REPO_DIR"
    PRE_DEPLOY_COMMIT="$(git rev-parse HEAD)"
    log_info "Pre-deploy commit: $PRE_DEPLOY_COMMIT"

    require_clean_tree_except_config
    backup_config

    # Reset config file before pull to avoid local-config merge conflicts.
    git checkout -- "$CONFIG_REL_PATH" || true

    log_info "Updating repository from origin/$BRANCH"
    git fetch origin "$BRANCH"
    git checkout "$BRANCH"
    git pull --ff-only origin "$BRANCH"

    restore_config
    deploy_runtime_files
    deploy_frontend
    restart_api_service
    stop_any_active_recording

    if [[ "$RUN_SMOKE" -eq 1 ]]; then
        run_recording_smoke
    else
        log_warn "Recording smoke check skipped (--no-smoke)"
    fi

    trap - ERR
    log_success "Deploy complete"
    log_info "Current commit: $(git rev-parse --short HEAD)"
}

main "$@"
