"""
Sync strategy: Local is source of truth.

When internet is available, the local instance pushes a full snapshot
to the hosted instance via a simple REST API call.

The hosted instance accepts the snapshot and replaces its data for that tournament.
This avoids complex conflict resolution: local always wins.
"""

import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models.db_models import (
    Tournament, Division, Competitor, Match, AuditLog, SyncLog
)
from app.config import settings

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


def export_tournament_snapshot(db: Session, tournament_id: int) -> dict:
    """Export a full tournament snapshot as a JSON-serializable dict."""
    tournament = db.query(Tournament).get(tournament_id)
    if not tournament:
        raise ValueError("Tournament not found")

    divisions = db.query(Division).filter(Division.tournament_id == tournament_id).all()
    snapshot = {
        "exported_at": datetime.utcnow().isoformat(),
        "tournament": {
            "id": tournament.id,
            "name": tournament.name,
            "date": tournament.date,
            "venue": tournament.venue,
            "num_rings": tournament.num_rings,
            "start_time": tournament.start_time,
            "bout_duration_minutes": tournament.bout_duration_minutes,
            "break_duration_minutes": tournament.break_duration_minutes,
            "buffer_minutes": tournament.buffer_minutes,
            "no_show_policy": tournament.no_show_policy.value if hasattr(tournament.no_show_policy, 'value') else tournament.no_show_policy,
        },
        "divisions": [],
        "audit_log_count": db.query(AuditLog).filter(AuditLog.tournament_id == tournament_id).count(),
    }

    for div in divisions:
        competitors = db.query(Competitor).filter(Competitor.division_id == div.id).all()
        matches = db.query(Match).filter(Match.division_id == div.id).all()

        div_data = {
            "id": div.id,
            "name": div.name,
            "weight_class_min": div.weight_class_min,
            "weight_class_max": div.weight_class_max,
            "gender": div.gender,
            "age_group": div.age_group,
            "experience_level": div.experience_level,
            "bracket_generated": div.bracket_generated,
            "bracket_started": div.bracket_started,
            "competitors": [
                {
                    "id": c.id,
                    "full_name": c.full_name,
                    "declared_weight": c.declared_weight,
                    "gym_team": c.gym_team,
                    "seed": c.seed,
                    "status": c.status.value if hasattr(c.status, 'value') else c.status,
                }
                for c in competitors
            ],
            "matches": [
                {
                    "id": m.id,
                    "round_number": m.round_number,
                    "position": m.position,
                    "competitor1_id": m.competitor1_id,
                    "competitor2_id": m.competitor2_id,
                    "winner_id": m.winner_id,
                    "next_match_id": m.next_match_id,
                    "is_bye": m.is_bye,
                    "status": m.status.value if hasattr(m.status, 'value') else m.status,
                    "result_method": (m.result_method.value if hasattr(m.result_method, 'value') else m.result_method) if m.result_method else None,
                    "ring_number": m.ring_number,
                    "scheduled_time": m.scheduled_time,
                    "queue_position": m.queue_position,
                    "notes": m.notes,
                }
                for m in matches
            ],
        }
        snapshot["divisions"].append(div_data)

    return snapshot


def push_to_hosted(db: Session, tournament_id: int,
                    target_url: Optional[str] = None,
                    api_key: Optional[str] = None) -> dict:
    """Push tournament snapshot to hosted instance."""
    if not HAS_HTTPX:
        return {"status": "failed", "error": "httpx not installed"}

    url = target_url or settings.SYNC_TARGET_URL
    key = api_key or settings.SYNC_API_KEY

    if not url:
        return {"status": "failed", "error": "No sync target URL configured"}

    snapshot = export_tournament_snapshot(db, tournament_id)

    sync_log = SyncLog(
        tournament_id=tournament_id,
        sync_type="full",
        status="in_progress",
    )
    db.add(sync_log)
    db.flush()

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{url}/api/sync/import",
                json=snapshot,
                headers={"Authorization": f"Bearer {key}"} if key else {},
            )
            resp.raise_for_status()

        sync_log.status = "success"
        sync_log.records_synced = (
            len(snapshot.get("divisions", []))
            + sum(len(d.get("competitors", [])) for d in snapshot.get("divisions", []))
            + sum(len(d.get("matches", [])) for d in snapshot.get("divisions", []))
        )
        db.commit()
        return {"status": "success", "records": sync_log.records_synced}

    except Exception as e:
        sync_log.status = "failed"
        sync_log.error_message = str(e)
        db.commit()
        return {"status": "failed", "error": str(e)}


def import_tournament_snapshot(db: Session, snapshot: dict) -> dict:
    """Import a tournament snapshot (used by hosted instance)."""
    t_data = snapshot["tournament"]

    # Upsert tournament
    tournament = db.query(Tournament).filter(Tournament.id == t_data["id"]).first()
    if tournament:
        for k, v in t_data.items():
            if k != "id":
                setattr(tournament, k, v)
    else:
        tournament = Tournament(**t_data)
        db.add(tournament)
    db.flush()

    # Process divisions
    for div_data in snapshot.get("divisions", []):
        div = db.query(Division).filter(Division.id == div_data["id"]).first()
        if div:
            # Update
            for k in ["name", "weight_class_min", "weight_class_max", "gender",
                       "age_group", "experience_level", "bracket_generated", "bracket_started"]:
                setattr(div, k, div_data.get(k))
        else:
            div = Division(
                id=div_data["id"],
                tournament_id=tournament.id,
                name=div_data["name"],
                weight_class_min=div_data.get("weight_class_min"),
                weight_class_max=div_data.get("weight_class_max"),
                gender=div_data.get("gender"),
                age_group=div_data.get("age_group"),
                experience_level=div_data.get("experience_level"),
                bracket_generated=div_data.get("bracket_generated", False),
                bracket_started=div_data.get("bracket_started", False),
            )
            db.add(div)
        db.flush()

        # Upsert competitors
        for c_data in div_data.get("competitors", []):
            comp = db.query(Competitor).filter(Competitor.id == c_data["id"]).first()
            if comp:
                for k, v in c_data.items():
                    if k not in ("id",):
                        setattr(comp, k, v)
            else:
                comp = Competitor(division_id=div.id, **c_data)
                db.add(comp)
        db.flush()

        # Upsert matches
        for m_data in div_data.get("matches", []):
            match = db.query(Match).filter(Match.id == m_data["id"]).first()
            if match:
                for k, v in m_data.items():
                    if k not in ("id",):
                        setattr(match, k, v)
            else:
                match = Match(division_id=div.id, **m_data)
                db.add(match)
        db.flush()

    db.commit()
    return {"status": "success", "tournament_id": tournament.id}
