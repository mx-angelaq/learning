"""Public self-registration + admin review endpoints."""

import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin
from app.models.db_models import (
    Registration, RegistrationStatus, Tournament, Division,
    Competitor, CompetitorStatus, AuditLog
)
from app.models.schemas import (
    RegistrationSubmit, RegistrationResponse, RegistrationReview
)

router = APIRouter(prefix="/api/tournaments/{tournament_id}/registrations", tags=["registrations"])


def _registration_to_response(reg: Registration, db: Session) -> dict:
    div = db.query(Division).filter(Division.id == reg.division_id).first()
    data = {c.key: getattr(reg, c.key) for c in reg.__table__.columns}
    data["division_name"] = div.name if div else None
    data["status"] = reg.status.value if hasattr(reg.status, "value") else reg.status
    return data


def _send_discord_webhook(registration: Registration, tournament: Tournament, division_name: str):
    """Fire-and-forget Discord webhook notification. Fails silently."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        return
    try:
        import httpx
        payload = {
            "content": None,
            "embeds": [{
                "title": "New Tournament Registration",
                "color": 3447003,
                "fields": [
                    {"name": "Name", "value": registration.full_name, "inline": True},
                    {"name": "Division", "value": division_name, "inline": True},
                    {"name": "Email", "value": registration.email, "inline": True},
                    {"name": "Gym/Team", "value": registration.gym_team or "N/A", "inline": True},
                    {"name": "Weight", "value": f"{registration.declared_weight} kg" if registration.declared_weight else "N/A", "inline": True},
                    {"name": "Tournament", "value": tournament.name, "inline": False},
                ],
                "footer": {"text": f"Registration #{registration.id} - Pending review"},
            }],
        }
        with httpx.Client(timeout=5) as client:
            client.post(webhook_url, json=payload)
    except Exception:
        pass  # Discord notification is best-effort


# --- Public endpoint: submit registration ---

@router.post("", response_model=RegistrationResponse)
def submit_registration(tournament_id: int, data: RegistrationSubmit,
                        db: Session = Depends(get_db)):
    """Public endpoint - no auth required. Submits a pending registration."""
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(404, "Tournament not found.")
    if not tournament.registration_open:
        raise HTTPException(400, "Registration is not currently open for this tournament.")

    # Validate division belongs to this tournament
    division = db.query(Division).filter(
        Division.id == data.division_id,
        Division.tournament_id == tournament_id,
    ).first()
    if not division:
        raise HTTPException(400, "Selected division does not exist in this tournament.")

    if not data.waiver_agreed:
        raise HTTPException(400, "You must agree to the waiver to register.")

    # Duplicate check: same email + same tournament
    existing = db.query(Registration).filter(
        Registration.tournament_id == tournament_id,
        Registration.email == data.email,
        Registration.status != RegistrationStatus.REJECTED,
    ).first()
    if existing:
        raise HTTPException(
            409,
            f"A registration for '{data.email}' already exists for this tournament "
            f"(status: {existing.status.value if hasattr(existing.status, 'value') else existing.status}). "
            "Contact the organizer if you need to make changes."
        )

    reg = Registration(
        tournament_id=tournament_id,
        division_id=data.division_id,
        full_name=data.full_name,
        email=data.email,
        declared_weight=data.declared_weight,
        gym_team=data.gym_team,
        phone=data.phone,
        age=data.age,
        experience_level=data.experience_level,
        waiver_agreed=data.waiver_agreed,
        status=RegistrationStatus.PENDING,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    # Discord notification (best-effort)
    _send_discord_webhook(reg, tournament, division.name)

    return _registration_to_response(reg, db)


# --- Public: check registration status by email ---

@router.get("/check")
def check_registration(tournament_id: int, email: str, db: Session = Depends(get_db)):
    """Public endpoint to check registration status by email."""
    reg = db.query(Registration).filter(
        Registration.tournament_id == tournament_id,
        Registration.email == email.strip().lower(),
    ).order_by(Registration.created_at.desc()).first()
    if not reg:
        raise HTTPException(404, "No registration found for this email.")
    return _registration_to_response(reg, db)


# --- Admin: list all registrations ---

@router.get("", response_model=List[RegistrationResponse])
def list_registrations(tournament_id: int, status: Optional[str] = None,
                       db: Session = Depends(get_db),
                       role: str = Depends(require_admin)):
    query = db.query(Registration).filter(Registration.tournament_id == tournament_id)
    if status:
        query = query.filter(Registration.status == status)
    regs = query.order_by(Registration.created_at.desc()).all()
    return [_registration_to_response(r, db) for r in regs]


# --- Admin: review (approve/reject) a registration ---

@router.post("/{registration_id}/review", response_model=RegistrationResponse)
def review_registration(tournament_id: int, registration_id: int,
                        data: RegistrationReview,
                        db: Session = Depends(get_db),
                        role: str = Depends(require_admin)):
    reg = db.query(Registration).filter(
        Registration.id == registration_id,
        Registration.tournament_id == tournament_id,
    ).first()
    if not reg:
        raise HTTPException(404, "Registration not found.")
    if reg.status != RegistrationStatus.PENDING:
        raise HTTPException(
            400,
            f"Registration is already {reg.status.value if hasattr(reg.status, 'value') else reg.status}. "
            "Only pending registrations can be reviewed."
        )

    if data.admin_notes:
        reg.admin_notes = data.admin_notes

    if data.action == "reject":
        reg.status = RegistrationStatus.REJECTED
        db.commit()
        db.refresh(reg)

        log = AuditLog(
            tournament_id=tournament_id,
            action="registration_rejected",
            entity_type="registration",
            entity_id=reg.id,
            details={"email": reg.email, "name": reg.full_name},
            performed_by="admin",
            reason=data.admin_notes,
        )
        db.add(log)
        db.commit()

        return _registration_to_response(reg, db)

    # --- Approve: create a Competitor via the same path admin uses ---
    division = db.query(Division).filter(Division.id == reg.division_id).first()
    if not division:
        raise HTTPException(400, "Division no longer exists. Cannot approve.")

    comp = Competitor(
        division_id=reg.division_id,
        full_name=reg.full_name,
        declared_weight=reg.declared_weight,
        gym_team=reg.gym_team,
        email=reg.email,
        phone=reg.phone,
        age=reg.age,
        waiver_signed=reg.waiver_agreed,
        status=CompetitorStatus.ACTIVE,
    )
    db.add(comp)
    db.flush()

    reg.status = RegistrationStatus.APPROVED
    reg.competitor_id = comp.id

    log = AuditLog(
        tournament_id=tournament_id,
        action="registration_approved",
        entity_type="registration",
        entity_id=reg.id,
        details={
            "email": reg.email,
            "name": reg.full_name,
            "competitor_id": comp.id,
            "division_id": reg.division_id,
        },
        performed_by="admin",
        reason=data.admin_notes,
    )
    db.add(log)
    db.commit()
    db.refresh(reg)

    return _registration_to_response(reg, db)


# --- Admin: get single registration ---

@router.get("/{registration_id}", response_model=RegistrationResponse)
def get_registration(tournament_id: int, registration_id: int,
                     db: Session = Depends(get_db),
                     role: str = Depends(require_admin)):
    reg = db.query(Registration).filter(
        Registration.id == registration_id,
        Registration.tournament_id == tournament_id,
    ).first()
    if not reg:
        raise HTTPException(404, "Registration not found.")
    return _registration_to_response(reg, db)
