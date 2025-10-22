# FootballVision Pro Platform

The platform layer provides the FastAPI backend, SQLite persistence, and the web dashboard that control match recording, preview streaming, and downloads.

## Structure
- `simple_api.py` – unified FastAPI application used by the device service
- `api-server/routers/` – modular endpoints for recording, preview, matches, uploads, and activity logging
- `api-server/services/` – background workers (auto-processor, SFTP uploads, notifications)
- `database/` – SQLite schema and helper used by the API
- `web-dashboard/` – React + TypeScript dashboard (Vite build) powering the UI and matches tab
- `installer/` – optional Nginx deploy script for serving the built dashboard on-device

## Key Features
- Start/stop dual-camera recordings via `/api/v1/recording`
- Launch/stop the optimized preview stream via `/api/v1/preview`
- Surface match manifests and downloads in the matches tab (`/api/v1/matches`)
- Track background processing and uploads through the auto-processor
- Emit Prometheus metrics for system health and pipeline status

## Local Development
1. Install Python dependencies from `requirements.txt` at the repository root.
2. Run the API:
   ```bash
   uvicorn src.platform.simple_api:app --reload --host 0.0.0.0 --port 8000
   ```
3. Install frontend dependencies:
   ```bash
   cd src/platform/web-dashboard
   npm install
   npm run dev
   ```
4. Access the dashboard at `http://localhost:5173` (development) or via the built `dist/` output.

## Configuration
Create `src/platform/api-server/.env` with credentials used by the upload and notification services:
```
SFTP_HOST=your-sftp-host
SFTP_USERNAME=your-user
SFTP_PASSWORD=secret
SFTP_REMOTE_DIR=/recordings
JWT_SECRET_KEY=change-me
```

The API writes the SQLite database to `/var/lib/footballvision/footballvision.db` and stores match artifacts under `/mnt/recordings`. Ensure those paths exist and are writable by the service user.
