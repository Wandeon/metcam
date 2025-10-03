"""
W37: Match Management
CRUD operations for match recordings
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
from pathlib import Path

router = APIRouter(prefix="/api/v1/matches", tags=["Matches"])

class Match(BaseModel):
    id: str
    home_team: str
    away_team: str
    date: str
    venue: Optional[str] = None
    duration_seconds: Optional[int] = None
    files: List[str] = []
    status: str  # recording, processing, completed
    created_at: str

class MatchCreate(BaseModel):
    id: str
    home_team: str
    away_team: str
    venue: Optional[str] = None

# In-memory storage (would be SQLite/PostgreSQL in production)
matches_db = {}

RECORDINGS_PATH = "/mnt/recordings"

@router.get("", response_model=List[Match])
async def list_matches(status: Optional[str] = None, limit: int = 100):
    """
    List all matches

    Args:
        status: Filter by status (recording/processing/completed)
        limit: Maximum number of matches to return

    Returns:
        List of matches
    """
    matches = list(matches_db.values())

    if status:
        matches = [m for m in matches if m["status"] == status]

    # Also scan filesystem for recordings
    try:
        recording_files = {}
        for file in Path(RECORDINGS_PATH).glob("*.mp4"):
            # Parse filename: match_id_cam0.mp4
            parts = file.stem.split('_')
            if len(parts) >= 2:
                match_id = '_'.join(parts[:-1])  # Everything except cam ID
                if match_id not in recording_files:
                    recording_files[match_id] = []
                recording_files[match_id].append(str(file))

        # Create matches from files if not in database
        for match_id, files in recording_files.items():
            if match_id not in matches_db:
                matches_db[match_id] = {
                    "id": match_id,
                    "home_team": "Unknown",
                    "away_team": "Unknown",
                    "date": datetime.now().isoformat(),
                    "files": files,
                    "status": "completed",
                    "created_at": datetime.now().isoformat()
                }
                matches.append(matches_db[match_id])

    except Exception as e:
        pass  # Filesystem scan failed, just return database matches

    return matches[:limit]

@router.post("", response_model=Match)
async def create_match(match: MatchCreate):
    """
    Create new match record

    Args:
        match: Match details

    Returns:
        Created match
    """
    if match.id in matches_db:
        raise HTTPException(status_code=400, detail="Match already exists")

    match_data = {
        "id": match.id,
        "home_team": match.home_team,
        "away_team": match.away_team,
        "date": datetime.now().isoformat(),
        "venue": match.venue,
        "files": [],
        "status": "recording",
        "created_at": datetime.now().isoformat()
    }

    matches_db[match.id] = match_data

    return Match(**match_data)

@router.get("/{match_id}", response_model=Match)
async def get_match(match_id: str):
    """
    Get match details

    Args:
        match_id: Match identifier

    Returns:
        Match details including file paths
    """
    if match_id not in matches_db:
        # Try to find from filesystem
        files = list(Path(RECORDINGS_PATH).glob(f"{match_id}*.mp4"))
        if not files:
            raise HTTPException(status_code=404, detail="Match not found")

        # Create match from files
        match_data = {
            "id": match_id,
            "home_team": "Unknown",
            "away_team": "Unknown",
            "date": datetime.now().isoformat(),
            "files": [str(f) for f in files],
            "status": "completed",
            "created_at": datetime.now().isoformat()
        }
        matches_db[match_id] = match_data

    return Match(**matches_db[match_id])

@router.put("/{match_id}")
async def update_match(match_id: str, match: MatchCreate):
    """
    Update match details

    Args:
        match_id: Match identifier
        match: Updated match data

    Returns:
        Updated match
    """
    if match_id not in matches_db:
        raise HTTPException(status_code=404, detail="Match not found")

    matches_db[match_id].update({
        "home_team": match.home_team,
        "away_team": match.away_team,
        "venue": match.venue
    })

    return Match(**matches_db[match_id])

@router.delete("/{match_id}")
async def delete_match(match_id: str, delete_files: bool = False):
    """
    Delete match record and optionally files

    Args:
        match_id: Match identifier
        delete_files: Whether to delete recording files

    Returns:
        Deletion confirmation
    """
    if match_id not in matches_db:
        raise HTTPException(status_code=404, detail="Match not found")

    match = matches_db[match_id]

    # Delete files if requested
    files_deleted = 0
    if delete_files:
        for file_path in match.get("files", []):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    files_deleted += 1
            except Exception as e:
                pass  # Continue deleting other files

    # Remove from database
    del matches_db[match_id]

    return {
        "status": "deleted",
        "match_id": match_id,
        "files_deleted": files_deleted
    }

@router.get("/{match_id}/download/{camera}")
async def download_recording(match_id: str, camera: str):
    """
    Get download URL for match recording

    Args:
        match_id: Match identifier
        camera: Camera ID (cam0, cam1, or panorama)

    Returns:
        Download URL or file path
    """
    filename = f"{match_id}_{camera}.mp4"
    file_path = Path(RECORDINGS_PATH) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    return {
        "match_id": match_id,
        "camera": camera,
        "filename": filename,
        "path": str(file_path),
        "size_mb": file_path.stat().st_size / (1024 * 1024),
        "download_url": f"/recordings/{filename}"
    }
