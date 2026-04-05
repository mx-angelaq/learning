"""Competitor CRUD + bulk operations."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin
from app.models.db_models import Competitor, Division, CompetitorStatus, AuditLog
from app.models.schemas import (
    CompetitorCreate, CompetitorUpdate, CompetitorBulkCreate,
    CompetitorResponse, DivisionChangeRequest
)

router = APIRouter(
    prefix="/api/tournaments/{tournament_id}/divisions/{division_id}/competitors",
    tags=["competitors"],
)


def _check_duplicate(db: Session, division_id: int, full_name: str,
                      gym_team: Optional[str], exclude_id: int = None) -> Optional[str]:
    """Check for potential duplicate competitors."""
    query = db.query(Competitor).filter(
        Competitor.division_id == division_id,
        Competitor.full_name == full_name.strip(),
        Competitor.status == CompetitorStatus.ACTIVE,
    )
    if exclude_id:
        query = query.filter(Competitor.id != exclude_id)
    if gym_team:
        query = query.filter(Competitor.gym_team == gym_team.strip())

    existing = query.first()
    if existing:
        return (f"Possible duplicate: '{full_name}' from '{gym_team or 'no gym'}' "
                f"already exists (ID: {existing.id}). Use force=true to override.")
    return None


@router.get("", response_model=List[CompetitorResponse])
def list_competitors(tournament_id: int, division_id: int,
                     db: Session = Depends(get_db)):
    return (
        db.query(Competitor)
        .filter(Competitor.division_id == division_id)
        .order_by(Competitor.seed.nullslast(), Competitor.full_name)
        .all()
    )


@router.post("", response_model=CompetitorResponse)
def create_competitor(tournament_id: int, division_id: int,
                      data: CompetitorCreate,
                      force: bool = Query(False),
                      db: Session = Depends(get_db),
                      role: str = Depends(require_admin)):
    div = db.query(Division).filter(
        Division.id == division_id, Division.tournament_id == tournament_id
    ).first()
    if not div:
        raise HTTPException(404, "Division not found.")

    if not force:
        dup = _check_duplicate(db, division_id, data.full_name, data.gym_team)
        if dup:
            raise HTTPException(409, dup)

    comp = Competitor(division_id=division_id, **data.model_dump())
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


@router.post("/bulk", response_model=List[CompetitorResponse])
def bulk_create_competitors(tournament_id: int, division_id: int,
                            data: CompetitorBulkCreate,
                            force: bool = Query(False),
                            db: Session = Depends(get_db),
                            role: str = Depends(require_admin)):
    div = db.query(Division).filter(
        Division.id == division_id, Division.tournament_id == tournament_id
    ).first()
    if not div:
        raise HTTPException(404, "Division not found.")

    results = []
    warnings = []
    for i, c_data in enumerate(data.competitors):
        if not force:
            dup = _check_duplicate(db, division_id, c_data.full_name, c_data.gym_team)
            if dup:
                warnings.append(f"Row {i+1}: {dup}")
                continue
        comp = Competitor(division_id=division_id, **c_data.model_dump())
        db.add(comp)
        db.flush()
        results.append(comp)

    db.commit()
    for c in results:
        db.refresh(c)
    return results


@router.get("/{competitor_id}", response_model=CompetitorResponse)
def get_competitor(tournament_id: int, division_id: int, competitor_id: int,
                   db: Session = Depends(get_db)):
    comp = db.query(Competitor).filter(
        Competitor.id == competitor_id, Competitor.division_id == division_id
    ).first()
    if not comp:
        raise HTTPException(404, "Competitor not found.")
    return comp


@router.put("/{competitor_id}", response_model=CompetitorResponse)
def update_competitor(tournament_id: int, division_id: int, competitor_id: int,
                      data: CompetitorUpdate, db: Session = Depends(get_db),
                      role: str = Depends(require_admin)):
    comp = db.query(Competitor).filter(
        Competitor.id == competitor_id, Competitor.division_id == division_id
    ).first()
    if not comp:
        raise HTTPException(404, "Competitor not found.")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(comp, key, value)
    db.commit()
    db.refresh(comp)
    return comp


@router.delete("/{competitor_id}")
def delete_competitor(tournament_id: int, division_id: int, competitor_id: int,
                      db: Session = Depends(get_db),
                      role: str = Depends(require_admin)):
    comp = db.query(Competitor).filter(
        Competitor.id == competitor_id, Competitor.division_id == division_id
    ).first()
    if not comp:
        raise HTTPException(404, "Competitor not found.")

    div = db.query(Division).get(division_id)
    if div and div.bracket_generated:
        raise HTTPException(
            400,
            "Cannot delete competitor after bracket is generated. "
            "Use withdrawal instead."
        )
    db.delete(comp)
    db.commit()
    return {"message": "Competitor deleted."}


@router.post("/{competitor_id}/change-division")
def change_division(tournament_id: int, division_id: int, competitor_id: int,
                    data: DivisionChangeRequest, db: Session = Depends(get_db),
                    role: str = Depends(require_admin)):
    comp = db.query(Competitor).filter(
        Competitor.id == competitor_id, Competitor.division_id == division_id
    ).first()
    if not comp:
        raise HTTPException(404, "Competitor not found.")

    new_div = db.query(Division).filter(
        Division.id == data.new_division_id, Division.tournament_id == tournament_id
    ).first()
    if not new_div:
        raise HTTPException(404, "Target division not found.")

    old_div = db.query(Division).get(division_id)
    warnings = []
    if old_div and old_div.bracket_generated:
        warnings.append("Source division bracket is generated. Competitor will be removed from it.")
    if new_div.bracket_generated:
        warnings.append("Target division bracket is already generated. Competitor won't be in bracket until regeneration.")

    comp.division_id = data.new_division_id

    # Audit
    log = AuditLog(
        tournament_id=tournament_id,
        action="division_change",
        entity_type="competitor",
        entity_id=competitor_id,
        details={
            "old_division_id": division_id,
            "new_division_id": data.new_division_id,
            "warnings": warnings,
        },
        performed_by="admin",
        reason=data.reason,
    )
    db.add(log)
    db.commit()

    return {
        "message": f"Competitor moved to division {data.new_division_id}.",
        "warnings": warnings,
    }
