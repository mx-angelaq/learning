"""Sync routes for local->hosted publishing."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin
from app.models.schemas import SyncRequest
from app.services.sync import export_tournament_snapshot, push_to_hosted, import_tournament_snapshot

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/export/{tournament_id}")
def export_snapshot(tournament_id: int, db: Session = Depends(get_db),
                    role: str = Depends(require_admin)):
    try:
        snapshot = export_tournament_snapshot(db, tournament_id)
        return snapshot
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/push/{tournament_id}")
def push_sync(tournament_id: int, data: SyncRequest = None,
              db: Session = Depends(get_db),
              role: str = Depends(require_admin)):
    target = data.target_url if data else None
    key = data.api_key if data else None
    result = push_to_hosted(db, tournament_id, target, key)
    if result["status"] == "failed":
        raise HTTPException(500, result.get("error", "Sync failed"))
    return result


@router.post("/import")
def import_snapshot(snapshot: dict, db: Session = Depends(get_db)):
    """Endpoint used by hosted instance to receive data from local."""
    try:
        result = import_tournament_snapshot(db, snapshot)
        return result
    except Exception as e:
        raise HTTPException(400, f"Import failed: {str(e)}")
