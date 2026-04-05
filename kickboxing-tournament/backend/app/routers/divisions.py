"""Division CRUD routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin
from app.models.db_models import Division, Competitor, CompetitorStatus
from app.models.schemas import DivisionCreate, DivisionResponse

router = APIRouter(prefix="/api/tournaments/{tournament_id}/divisions", tags=["divisions"])


def _division_response(div: Division, db: Session) -> dict:
    count = db.query(Competitor).filter(
        Competitor.division_id == div.id,
        Competitor.status == CompetitorStatus.ACTIVE
    ).count()
    return {
        **{c.key: getattr(div, c.key) for c in div.__table__.columns},
        "competitor_count": count,
    }


@router.get("", response_model=List[DivisionResponse])
def list_divisions(tournament_id: int, db: Session = Depends(get_db)):
    divs = db.query(Division).filter(Division.tournament_id == tournament_id).all()
    return [_division_response(d, db) for d in divs]


@router.get("/{division_id}", response_model=DivisionResponse)
def get_division(tournament_id: int, division_id: int, db: Session = Depends(get_db)):
    div = db.query(Division).filter(
        Division.id == division_id, Division.tournament_id == tournament_id
    ).first()
    if not div:
        raise HTTPException(404, "Division not found.")
    return _division_response(div, db)


@router.post("", response_model=DivisionResponse)
def create_division(tournament_id: int, data: DivisionCreate,
                    db: Session = Depends(get_db), role: str = Depends(require_admin)):
    div = Division(tournament_id=tournament_id, **data.model_dump())
    db.add(div)
    db.commit()
    db.refresh(div)
    return _division_response(div, db)


@router.put("/{division_id}", response_model=DivisionResponse)
def update_division(tournament_id: int, division_id: int, data: DivisionCreate,
                    db: Session = Depends(get_db), role: str = Depends(require_admin)):
    div = db.query(Division).filter(
        Division.id == division_id, Division.tournament_id == tournament_id
    ).first()
    if not div:
        raise HTTPException(404, "Division not found.")
    for key, value in data.model_dump().items():
        setattr(div, key, value)
    db.commit()
    db.refresh(div)
    return _division_response(div, db)


@router.delete("/{division_id}")
def delete_division(tournament_id: int, division_id: int,
                    db: Session = Depends(get_db), role: str = Depends(require_admin)):
    div = db.query(Division).filter(
        Division.id == division_id, Division.tournament_id == tournament_id
    ).first()
    if not div:
        raise HTTPException(404, "Division not found.")
    if div.bracket_started:
        raise HTTPException(400, "Cannot delete a division with started matches. Remove matches first.")
    db.delete(div)
    db.commit()
    return {"message": "Division deleted."}
