"""Scheduling and ring queue management routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_staff_or_admin
from app.models.db_models import Match, Division, Competitor, MatchStatus
from app.models.schemas import MatchResponse, ReorderRequest
from app.services.scheduling import estimate_match_times, get_ring_queue, reorder_ring_queue

router = APIRouter(prefix="/api/tournaments/{tournament_id}/scheduling", tags=["scheduling"])


@router.get("/estimate")
def get_schedule_estimate(tournament_id: int, db: Session = Depends(get_db)):
    return estimate_match_times(db, tournament_id)


@router.get("/rings/{ring_number}")
def get_ring_matches(tournament_id: int, ring_number: int,
                     db: Session = Depends(get_db)):
    queue = get_ring_queue(db, tournament_id, ring_number)

    def match_to_dict(m):
        c1 = db.query(Competitor).get(m.competitor1_id) if m.competitor1_id else None
        c2 = db.query(Competitor).get(m.competitor2_id) if m.competitor2_id else None
        return {
            "id": m.id,
            "round_number": m.round_number,
            "competitor1_name": c1.full_name if c1 else "TBD",
            "competitor2_name": c2.full_name if c2 else "TBD",
            "status": m.status.value if hasattr(m.status, 'value') else m.status,
            "scheduled_time": m.scheduled_time,
            "division_id": m.division_id,
        }

    return {
        "ring_number": ring_number,
        "in_progress": [match_to_dict(m) for m in queue["in_progress"]],
        "on_deck": [match_to_dict(m) for m in queue["on_deck"]],
        "queued": [match_to_dict(m) for m in queue["queued"]],
        "completed": [match_to_dict(m) for m in queue["completed"]],
    }


@router.put("/rings/{ring_number}/reorder")
def reorder_matches(tournament_id: int, ring_number: int,
                    data: ReorderRequest, db: Session = Depends(get_db),
                    role: str = Depends(require_staff_or_admin)):
    reorder_ring_queue(db, ring_number, data.match_ids)
    db.commit()
    return {"message": "Queue reordered."}
