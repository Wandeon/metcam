# FootballVision Pro - API Reference

## Base URL
```
http://<device-ip>:8000/api/v1
```

## Authentication
```http
Authorization: Bearer <jwt-token>
```

## Endpoints

### System Status
```http
GET /status
```
**Response**:
```json
{
  "status": "ready",
  "recording": false,
  "temperature_c": 45.2,
  "storage_gb": 120.5,
  "uptime_seconds": 3600
}
```

### Start Recording
```http
POST /recording/start
Content-Type: application/json

{
  "match_id": "match_20250930_001",
  "home_team": "Team A",
  "away_team": "Team B",
  "duration_minutes": 90
}
```

### Stop Recording
```http
POST /recording/stop
```

### Get Recordings
```http
GET /recordings
```

For complete API documentation, see OpenAPI spec: `src/platform/docs/openapi.yaml`