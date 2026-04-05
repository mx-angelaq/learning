"""Match scheduling and ring queue management."""

from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session

from app.models.db_models import Match, Tournament, Division, MatchStatus


def estimate_match_times(db: Session, tournament_id: int) -> List[Dict]:
    """
    Estimate start times for all pending/queued matches based on tournament settings.
    Distributes across rings.
    """
    tournament = db.query(Tournament).get(tournament_id)
    if not tournament:
        return []

    bout_mins = tournament.bout_duration_minutes
    break_mins = tournament.break_duration_minutes
    buffer_mins = tournament.buffer_minutes
    total_per_match = bout_mins + break_mins + buffer_mins
    num_rings = tournament.num_rings

    # Parse start time
    try:
        start = datetime.strptime(tournament.start_time, "%H:%M")
    except ValueError:
        start = datetime.strptime("09:00", "%H:%M")

    # Get matches ordered by round then position, excluding completed/cancelled/byes
    matches = (
        db.query(Match)
        .join(Division)
        .filter(
            Division.tournament_id == tournament_id,
            Match.status.in_([
                MatchStatus.PENDING, MatchStatus.QUEUED,
                MatchStatus.ON_DECK, MatchStatus.IN_PROGRESS
            ]),
            Match.is_bye == False,
        )
        .order_by(Match.queue_position.nullslast(), Match.round_number, Match.position)
        .all()
    )

    # Assign to rings round-robin
    ring_times = {r: start for r in range(1, num_rings + 1)}
    result = []

    for match in matches:
        # Find the ring with the earliest available time
        ring = min(ring_times, key=ring_times.get)
        est_time = ring_times[ring]

        result.append({
            "match_id": match.id,
            "ring_number": match.ring_number or ring,
            "estimated_time": est_time.strftime("%H:%M"),
            "division_id": match.division_id,
            "round_number": match.round_number,
            "status": match.status.value if hasattr(match.status, 'value') else match.status,
        })

        # Update match if not manually assigned
        if not match.ring_number:
            match.ring_number = ring
        if not match.scheduled_time:
            match.scheduled_time = est_time.strftime("%H:%M")

        ring_times[ring] = est_time + timedelta(minutes=total_per_match)

    db.flush()
    return result


def get_ring_queue(db: Session, tournament_id: int, ring_number: int) -> Dict:
    """Get the match queue for a specific ring."""
    matches = (
        db.query(Match)
        .join(Division)
        .filter(
            Division.tournament_id == tournament_id,
            Match.ring_number == ring_number,
            Match.is_bye == False,
        )
        .order_by(Match.queue_position.nullslast(), Match.round_number, Match.position)
        .all()
    )

    in_progress = [m for m in matches if m.status == MatchStatus.IN_PROGRESS]
    on_deck = [m for m in matches if m.status == MatchStatus.ON_DECK]
    queued = [m for m in matches if m.status == MatchStatus.QUEUED]
    completed = [m for m in matches if m.status == MatchStatus.COMPLETED]

    return {
        "ring_number": ring_number,
        "in_progress": in_progress,
        "on_deck": on_deck,
        "queued": queued,
        "completed": completed,
    }


def reorder_ring_queue(db: Session, ring_number: int, match_ids: List[int]):
    """Reorder matches in a ring queue by setting queue_position."""
    for idx, match_id in enumerate(match_ids):
        match = db.query(Match).get(match_id)
        if match and match.ring_number == ring_number:
            match.queue_position = idx
    db.flush()
