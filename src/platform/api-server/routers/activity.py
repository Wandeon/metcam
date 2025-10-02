"""
Activity log API endpoints
Provides access to system activity history with filtering and export
"""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "database"))
from db_manager import db

router = APIRouter(prefix="/api/v1/activity", tags=["Activity"])


@router.get("/")
async def get_activity_log(
    limit: int = 100,
    event_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    match_id: Optional[str] = None,
    severity: Optional[str] = None
):
    """
    Get filtered activity log from system_events table

    Args:
        limit: Maximum number of events to return
        event_type: Filter by event type
        start_date: Filter events after this date (ISO format)
        end_date: Filter events before this date (ISO format)
        match_id: Filter by match ID
        severity: Filter by severity (info, warning, error, critical)
    """
    query = "SELECT * FROM system_events WHERE 1=1"
    params = []

    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)

    if match_id:
        query += " AND match_id = ?"
        params.append(match_id)

    if severity:
        query += " AND severity = ?"
        params.append(severity)

    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)

    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    events = db.execute(query, tuple(params))
    return {'events': events, 'count': len(events)}


@router.get("/types")
async def get_event_types():
    """Get list of all event types"""
    result = db.execute(
        "SELECT DISTINCT event_type, COUNT(*) as count FROM system_events GROUP BY event_type ORDER BY count DESC"
    )
    return {'event_types': result}


@router.get("/export")
async def export_activity_log(
    format: str = "csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Export activity log to CSV or JSON

    Args:
        format: Export format (csv or json)
        start_date: Filter events after this date (ISO format)
        end_date: Filter events before this date (ISO format)
    """
    query = "SELECT * FROM system_events WHERE 1=1"
    params = []

    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)

    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)

    query += " ORDER BY timestamp DESC"

    events = db.execute(query, tuple(params))

    if format == "csv":
        # Generate CSV
        output = io.StringIO()
        if events:
            writer = csv.DictWriter(output, fieldnames=events[0].keys())
            writer.writeheader()
            writer.writerows(events)

        response = Response(content=output.getvalue(), media_type="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return response

    elif format == "json":
        import json
        response = Response(content=json.dumps({'events': events}, indent=2), media_type="application/json")
        response.headers["Content-Disposition"] = f"attachment; filename=activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return response

    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'csv' or 'json'")


@router.get("/stats")
async def get_activity_stats():
    """Get activity statistics"""
    stats = {
        'total_events': db.execute_one("SELECT COUNT(*) as count FROM system_events")['count'],
        'by_severity': db.execute("SELECT severity, COUNT(*) as count FROM system_events GROUP BY severity"),
        'by_component': db.execute("SELECT component, COUNT(*) as count FROM system_events GROUP BY component ORDER BY count DESC LIMIT 10"),
        'recent_errors': db.execute(
            "SELECT * FROM system_events WHERE severity IN ('error', 'critical') ORDER BY timestamp DESC LIMIT 10"
        )
    }
    return stats
