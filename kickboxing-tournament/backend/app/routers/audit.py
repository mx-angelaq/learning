"""Audit log routes."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import AuditLog
from app.models.schemas import AuditLogResponse

router = APIRouter(prefix="/api/tournaments/{tournament_id}/audit", tags=["audit"])


@router.get("", response_model=List[AuditLogResponse])
def get_audit_log(tournament_id: int, db: Session = Depends(get_db)):
    return (
        db.query(AuditLog)
        .filter(AuditLog.tournament_id == tournament_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )
