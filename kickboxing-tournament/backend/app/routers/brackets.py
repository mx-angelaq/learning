"""Bracket generation and match management routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin, require_staff_or_admin
from app.models.db_models import (
    Match, Division, Competitor, MatchStatus
)
from app.models.schemas import (
    MatchResponse, BracketGenerateRequest, RecordResultRequest,
    MatchStatusUpdate, WithdrawalRequest, SubstitutionRequest,
    ResultCorrectionRequest, NoShowRequest
)
from app.services.bracket_engine import (
    generate_bracket, advance_winner, handle_withdrawal,
    handle_no_show, handle_substitution, rollback_result,
    correct_result
)

router = APIRouter(
    prefix="/api/tournaments/{tournament_id}/divisions/{division_id}",
    tags=["brackets"],
)


def _match_to_response(match: Match, db: Session) -> dict:
    c1 = db.query(Competitor).get(match.competitor1_id) if match.competitor1_id else None
    c2 = db.query(Competitor).get(match.competitor2_id) if match.competitor2_id else None
    w = db.query(Competitor).get(match.winner_id) if match.winner_id else None
    return {
        "id": match.id,
        "division_id": match.division_id,
        "round_number": match.round_number,
        "position": match.position,
        "competitor1_id": match.competitor1_id,
        "competitor2_id": match.competitor2_id,
        "competitor1_name": c1.full_name if c1 else None,
        "competitor2_name": c2.full_name if c2 else None,
        "winner_id": match.winner_id,
        "winner_name": w.full_name if w else None,
        "next_match_id": match.next_match_id,
        "is_bye": match.is_bye,
        "status": match.status.value if hasattr(match.status, 'value') else match.status,
        "result_method": (match.result_method.value if hasattr(match.result_method, 'value') else match.result_method) if match.result_method else None,
        "ring_number": match.ring_number,
        "scheduled_time": match.scheduled_time,
        "queue_position": match.queue_position,
        "notes": match.notes,
    }


@router.post("/bracket", response_model=List[MatchResponse])
def generate_division_bracket(tournament_id: int, division_id: int,
                               data: BracketGenerateRequest,
                               db: Session = Depends(get_db),
                               role: str = Depends(require_admin)):
    div = db.query(Division).filter(
        Division.id == division_id, Division.tournament_id == tournament_id
    ).first()
    if not div:
        raise HTTPException(404, "Division not found.")

    matches, warning = generate_bracket(
        db, div, data.seeding, "admin", data.confirm_regenerate
    )
    if not matches and warning:
        raise HTTPException(400, warning)

    db.commit()
    return [_match_to_response(m, db) for m in matches]


@router.get("/bracket", response_model=List[MatchResponse])
def get_bracket(tournament_id: int, division_id: int,
                db: Session = Depends(get_db)):
    matches = (
        db.query(Match)
        .filter(Match.division_id == division_id)
        .order_by(Match.round_number, Match.position)
        .all()
    )
    return [_match_to_response(m, db) for m in matches]


@router.get("/matches/{match_id}", response_model=MatchResponse)
def get_match(tournament_id: int, division_id: int, match_id: int,
              db: Session = Depends(get_db)):
    match = db.query(Match).filter(
        Match.id == match_id, Match.division_id == division_id
    ).first()
    if not match:
        raise HTTPException(404, "Match not found.")
    return _match_to_response(match, db)


@router.post("/matches/{match_id}/result", response_model=MatchResponse)
def record_result(tournament_id: int, division_id: int, match_id: int,
                  data: RecordResultRequest, db: Session = Depends(get_db),
                  role: str = Depends(require_staff_or_admin)):
    match = db.query(Match).filter(
        Match.id == match_id, Match.division_id == division_id
    ).first()
    if not match:
        raise HTTPException(404, "Match not found.")
    if match.status == MatchStatus.COMPLETED:
        raise HTTPException(400, "Match already completed. Use correction endpoint to fix.")
    if match.is_bye:
        raise HTTPException(400, "Cannot record result for a bye match.")

    try:
        advance_winner(db, match, data.winner_id, data.result_method, "admin", data.notes)
        db.commit()
    except ValueError as e:
        raise HTTPException(400, str(e))

    return _match_to_response(match, db)


@router.put("/matches/{match_id}/status", response_model=MatchResponse)
def update_match_status(tournament_id: int, division_id: int, match_id: int,
                        data: MatchStatusUpdate, db: Session = Depends(get_db),
                        role: str = Depends(require_staff_or_admin)):
    match = db.query(Match).filter(
        Match.id == match_id, Match.division_id == division_id
    ).first()
    if not match:
        raise HTTPException(404, "Match not found.")

    match.status = data.status
    if data.ring_number is not None:
        match.ring_number = data.ring_number
    if data.queue_position is not None:
        match.queue_position = data.queue_position
    db.commit()
    return _match_to_response(match, db)


# --- Chaos scenario endpoints ---

@router.post("/matches/{match_id}/withdrawal", response_model=MatchResponse)
def withdraw_competitor(tournament_id: int, division_id: int, match_id: int,
                        competitor_id: int, data: WithdrawalRequest,
                        db: Session = Depends(get_db),
                        role: str = Depends(require_admin)):
    match = db.query(Match).filter(
        Match.id == match_id, Match.division_id == division_id
    ).first()
    if not match:
        raise HTTPException(404, "Match not found.")

    try:
        handle_withdrawal(db, match, competitor_id, data.reason, "admin")
        db.commit()
    except ValueError as e:
        raise HTTPException(400, str(e))

    return _match_to_response(match, db)


@router.post("/matches/{match_id}/no-show", response_model=MatchResponse)
def process_no_show(tournament_id: int, division_id: int, match_id: int,
                    competitor_id: int, data: NoShowRequest,
                    db: Session = Depends(get_db),
                    role: str = Depends(require_admin)):
    match = db.query(Match).filter(
        Match.id == match_id, Match.division_id == division_id
    ).first()
    if not match:
        raise HTTPException(404, "Match not found.")

    div = db.query(Division).get(division_id)
    tournament = div.tournament if div else None
    policy = tournament.no_show_policy.value if tournament and hasattr(tournament.no_show_policy, 'value') else "walkover"

    try:
        handle_no_show(db, match, competitor_id, policy, data.reason or "No show", "admin")
        db.commit()
    except ValueError as e:
        raise HTTPException(400, str(e))

    return _match_to_response(match, db)


@router.post("/matches/{match_id}/substitution", response_model=MatchResponse)
def substitute_competitor(tournament_id: int, division_id: int, match_id: int,
                          competitor_id: int, data: SubstitutionRequest,
                          db: Session = Depends(get_db),
                          role: str = Depends(require_admin)):
    match = db.query(Match).filter(
        Match.id == match_id, Match.division_id == division_id
    ).first()
    if not match:
        raise HTTPException(404, "Match not found.")

    div = db.query(Division).filter(
        Division.id == division_id, Division.tournament_id == tournament_id
    ).first()
    if not div:
        raise HTTPException(404, "Division not found.")

    try:
        handle_substitution(
            db, match, competitor_id,
            data.new_competitor.model_dump(), div,
            data.reason, "admin"
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(400, str(e))

    return _match_to_response(match, db)


@router.post("/matches/{match_id}/rollback", response_model=MatchResponse)
def rollback_match(tournament_id: int, division_id: int, match_id: int,
                   reason: str, db: Session = Depends(get_db),
                   role: str = Depends(require_admin)):
    match = db.query(Match).filter(
        Match.id == match_id, Match.division_id == division_id
    ).first()
    if not match:
        raise HTTPException(404, "Match not found.")

    try:
        rollback_result(db, match, reason, "admin")
        db.commit()
    except ValueError as e:
        raise HTTPException(400, str(e))

    return _match_to_response(match, db)


@router.post("/matches/{match_id}/correct", response_model=MatchResponse)
def correct_match_result(tournament_id: int, division_id: int, match_id: int,
                         data: ResultCorrectionRequest,
                         db: Session = Depends(get_db),
                         role: str = Depends(require_admin)):
    match = db.query(Match).filter(
        Match.id == match_id, Match.division_id == division_id
    ).first()
    if not match:
        raise HTTPException(404, "Match not found.")

    try:
        correct_result(db, match, data.correct_winner_id,
                        data.result_method, data.reason, "admin")
        db.commit()
    except ValueError as e:
        raise HTTPException(400, str(e))

    return _match_to_response(match, db)
