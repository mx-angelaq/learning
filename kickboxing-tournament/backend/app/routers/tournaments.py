"""Tournament CRUD routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin, get_current_role
from app.models.db_models import Tournament
from app.models.schemas import TournamentCreate, TournamentUpdate, TournamentResponse

DEFAULT_WEIGHT_PRESETS = [
    {"name": "Strawweight", "min_kg": None, "max_kg": 52.2},
    {"name": "Flyweight", "min_kg": 52.2, "max_kg": 56.7},
    {"name": "Bantamweight", "min_kg": 56.7, "max_kg": 61.2},
    {"name": "Featherweight", "min_kg": 61.2, "max_kg": 65.8},
    {"name": "Lightweight", "min_kg": 65.8, "max_kg": 70.3},
    {"name": "Welterweight", "min_kg": 70.3, "max_kg": 77.1},
    {"name": "Middleweight", "min_kg": 77.1, "max_kg": 83.9},
    {"name": "Light Heavyweight", "min_kg": 83.9, "max_kg": 93.0},
    {"name": "Heavyweight", "min_kg": 93.0, "max_kg": None},
]

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


@router.get("", response_model=List[TournamentResponse])
def list_tournaments(db: Session = Depends(get_db)):
    return db.query(Tournament).order_by(Tournament.date.desc()).all()


@router.get("/{tournament_id}", response_model=TournamentResponse)
def get_tournament(tournament_id: int, db: Session = Depends(get_db)):
    t = db.query(Tournament).get(tournament_id)
    if not t:
        raise HTTPException(404, "Tournament not found.")
    return t


@router.post("", response_model=TournamentResponse)
def create_tournament(data: TournamentCreate, db: Session = Depends(get_db),
                      role: str = Depends(require_admin)):
    t = Tournament(
        name=data.name,
        date=data.date,
        venue=data.venue,
        num_rings=data.num_rings,
        start_time=data.start_time,
        bout_duration_minutes=data.bout_duration_minutes,
        break_duration_minutes=data.break_duration_minutes,
        buffer_minutes=data.buffer_minutes,
        weighin_tolerance_kg=data.weighin_tolerance_kg,
        substitution_cutoff_round=data.substitution_cutoff_round,
        no_show_policy=data.no_show_policy,
        weight_presets=([p.model_dump() for p in data.weight_presets]
                        if data.weight_presets else DEFAULT_WEIGHT_PRESETS),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.put("/{tournament_id}", response_model=TournamentResponse)
def update_tournament(tournament_id: int, data: TournamentUpdate,
                      db: Session = Depends(get_db), role: str = Depends(require_admin)):
    t = db.query(Tournament).get(tournament_id)
    if not t:
        raise HTTPException(404, "Tournament not found.")
    update_data = data.model_dump(exclude_unset=True)
    if "weight_presets" in update_data and update_data["weight_presets"]:
        update_data["weight_presets"] = [p.model_dump() if hasattr(p, 'model_dump') else p
                                          for p in update_data["weight_presets"]]
    for key, value in update_data.items():
        setattr(t, key, value)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{tournament_id}")
def delete_tournament(tournament_id: int, db: Session = Depends(get_db),
                      role: str = Depends(require_admin)):
    t = db.query(Tournament).get(tournament_id)
    if not t:
        raise HTTPException(404, "Tournament not found.")
    db.delete(t)
    db.commit()
    return {"message": "Tournament deleted."}


@router.get("/{tournament_id}/weight-presets")
def get_weight_presets(tournament_id: int, db: Session = Depends(get_db)):
    t = db.query(Tournament).get(tournament_id)
    if not t:
        raise HTTPException(404, "Tournament not found.")
    return t.weight_presets or DEFAULT_WEIGHT_PRESETS
