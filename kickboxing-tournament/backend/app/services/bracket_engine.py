"""
Single-elimination bracket engine.

Supports:
- Any competitor count (non-power-of-two handled with byes)
- Seeding: random, manual, separate-gyms
- Safe regeneration with confirmation
- Day-of chaos: withdrawals, no-shows, substitutions, corrections
"""

import math
import random
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.db_models import (
    Match, Competitor, Division, AuditLog,
    MatchStatus, CompetitorStatus, ResultMethod
)


def _next_power_of_two(n: int) -> int:
    """Return the smallest power of 2 >= n."""
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def _create_audit(db: Session, tournament_id: int, action: str, entity_type: str,
                   entity_id: int = None, details: dict = None,
                   performed_by: str = "system", reason: str = None):
    log = AuditLog(
        tournament_id=tournament_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        performed_by=performed_by,
        reason=reason,
    )
    db.add(log)


def separate_gyms_seed(competitors: List[Competitor]) -> List[Competitor]:
    """
    Best-effort seeding to separate same-gym competitors in round 1.
    Groups by gym, then interleaves. If impossible (more from one gym than half),
    does best effort.
    """
    gym_groups = {}
    no_gym = []
    for c in competitors:
        key = (c.gym_team or "").strip().lower()
        if key:
            gym_groups.setdefault(key, []).append(c)
        else:
            no_gym.append(c)

    # Shuffle within each group
    for g in gym_groups.values():
        random.shuffle(g)
    random.shuffle(no_gym)

    # Sort groups by size descending
    sorted_groups = sorted(gym_groups.values(), key=len, reverse=True)

    # Interleave: place from largest group, then next, etc.
    result = []
    while sorted_groups or no_gym:
        for group in list(sorted_groups):
            if group:
                result.append(group.pop(0))
            if not group:
                sorted_groups.remove(group)
        if no_gym:
            result.append(no_gym.pop(0))

    return result


def generate_bracket(
    db: Session,
    division: Division,
    seeding: str = "random",
    performed_by: str = "admin",
    confirm_regenerate: bool = False,
) -> Tuple[List[Match], Optional[str]]:
    """
    Generate a single-elimination bracket for a division.

    Returns (matches, warning_message).
    """
    tournament_id = division.tournament_id

    # Check if bracket already exists
    existing_matches = db.query(Match).filter(Match.division_id == division.id).all()
    if existing_matches:
        if division.bracket_started and not confirm_regenerate:
            return [], "Bracket has started matches. Regenerating will DELETE all results. Set confirm_regenerate=true to proceed."
        if not confirm_regenerate and division.bracket_generated:
            return [], "Bracket already generated. Set confirm_regenerate=true to regenerate."

        # Log the regeneration
        _create_audit(db, tournament_id, "bracket_regenerated", "division",
                       division.id, {"previous_match_count": len(existing_matches)},
                       performed_by, "Bracket regenerated")
        # Delete existing matches
        for m in existing_matches:
            db.delete(m)
        db.flush()
        division.bracket_started = False

    # Get active competitors
    competitors = (
        db.query(Competitor)
        .filter(Competitor.division_id == division.id,
                Competitor.status == CompetitorStatus.ACTIVE)
        .all()
    )

    if len(competitors) < 2:
        return [], "Need at least 2 active competitors to generate a bracket."

    # Apply seeding
    warning = None
    if seeding == "random":
        random.shuffle(competitors)
    elif seeding == "manual":
        # Sort by seed field (nulls last)
        competitors.sort(key=lambda c: (c.seed is None, c.seed or 0))
    elif seeding == "separate_gyms":
        competitors = separate_gyms_seed(competitors)
        # Check if separation was perfect
        n = len(competitors)
        for i in range(0, n - 1, 2):
            if i + 1 < n:
                g1 = (competitors[i].gym_team or "").strip().lower()
                g2 = (competitors[i + 1].gym_team or "").strip().lower()
                if g1 and g2 and g1 == g2:
                    warning = "Could not fully separate all same-gym competitors in round 1. Best effort applied."
                    break

    n = len(competitors)
    bracket_size = _next_power_of_two(n)
    num_byes = bracket_size - n
    total_rounds = int(math.log2(bracket_size))

    # Create all match slots
    all_matches = []
    match_map = {}  # (round, position) -> Match

    for rnd in range(1, total_rounds + 1):
        matches_in_round = bracket_size >> rnd
        for pos in range(matches_in_round):
            match = Match(
                division_id=division.id,
                round_number=rnd,
                position=pos,
                status=MatchStatus.PENDING,
            )
            db.add(match)
            db.flush()
            all_matches.append(match)
            match_map[(rnd, pos)] = match

    # Link matches: winner of (round R, pos P) goes to (round R+1, pos P//2)
    for rnd in range(1, total_rounds):
        matches_in_round = bracket_size >> rnd
        for pos in range(matches_in_round):
            current = match_map[(rnd, pos)]
            next_match = match_map.get((rnd + 1, pos // 2))
            if next_match:
                current.next_match_id = next_match.id

    # Place competitors into first round slots.
    # Standard approach: top seeds get byes. Byes are spread across the bracket
    # by placing them at the bottom positions of round 1.
    first_round_count = bracket_size // 2

    # Build a list of (competitor1, competitor2) for each R1 match.
    # Byes are at the end: the last `num_byes` matches have only one competitor.
    # We pair: match 0 = seed 0 vs seed (bracket_size - 1),
    #          match 1 = seed 1 vs seed (bracket_size - 2), etc.
    # Simpler: top seeds paired with byes at bottom of bracket.
    # Place all real competitors first, byes fill remaining slots.
    for pos in range(first_round_count):
        match = match_map[(1, pos)]
        # Competitor 1 is seed index `pos`
        c1_idx = pos
        # Competitor 2 is the "mirror" from the bottom
        c2_idx = bracket_size - 1 - pos
        c1 = competitors[c1_idx] if c1_idx < n else None
        c2 = competitors[c2_idx] if c2_idx < n else None

        match.competitor1_id = c1.id if c1 else None
        match.competitor2_id = c2.id if c2 else None

        # Handle byes
        if c1 and not c2:
            match.is_bye = True
            match.status = MatchStatus.COMPLETED
            match.winner_id = c1.id
            match.result_method = ResultMethod.WALKOVER
        elif c2 and not c1:
            match.is_bye = True
            match.status = MatchStatus.COMPLETED
            match.winner_id = c2.id
            match.result_method = ResultMethod.WALKOVER
        elif not c1 and not c2:
            match.is_bye = True
            match.status = MatchStatus.COMPLETED

    db.flush()

    # Advance bye winners to next round
    for pos in range(first_round_count):
        match = match_map[(1, pos)]
        if match.is_bye and match.winner_id and match.next_match_id:
            next_m = match_map.get((2, pos // 2))
            if next_m:
                if pos % 2 == 0:
                    next_m.competitor1_id = match.winner_id
                else:
                    next_m.competitor2_id = match.winner_id

    division.bracket_generated = True
    db.flush()

    _create_audit(db, tournament_id, "bracket_generated", "division",
                   division.id,
                   {"competitor_count": n, "bracket_size": bracket_size,
                    "seeding": seeding, "byes": num_byes},
                   performed_by)

    return all_matches, warning


def advance_winner(db: Session, match: Match, winner_id: int,
                    result_method: str, performed_by: str = "admin",
                    notes: str = None):
    """Record a match result and advance the winner."""
    division = db.query(Division).get(match.division_id)
    if not division:
        raise ValueError("Division not found")

    # Validate winner is in this match
    if winner_id not in (match.competitor1_id, match.competitor2_id):
        raise ValueError(f"Winner (id={winner_id}) is not a competitor in this match.")

    match.winner_id = winner_id
    match.result_method = result_method
    match.status = MatchStatus.COMPLETED
    match.notes = notes

    # Mark division as started
    if not division.bracket_started:
        division.bracket_started = True

    # Advance to next match
    if match.next_match_id:
        next_match = db.query(Match).get(match.next_match_id)
        if next_match:
            if match.position % 2 == 0:
                next_match.competitor1_id = winner_id
            else:
                next_match.competitor2_id = winner_id

    _create_audit(db, division.tournament_id, "result_recorded", "match",
                   match.id,
                   {"winner_id": winner_id, "method": result_method},
                   performed_by, notes)

    db.flush()
    return match


def handle_withdrawal(db: Session, match: Match, competitor_id: int,
                       reason: str, performed_by: str = "admin"):
    """Handle a competitor withdrawal. Opponent advances."""
    division = db.query(Division).get(match.division_id)
    competitor = db.query(Competitor).get(competitor_id)

    if competitor_id not in (match.competitor1_id, match.competitor2_id):
        raise ValueError("Competitor is not in this match.")

    competitor.status = CompetitorStatus.WITHDRAWN

    # Determine opponent
    opponent_id = match.competitor2_id if competitor_id == match.competitor1_id else match.competitor1_id

    if opponent_id:
        advance_winner(db, match, opponent_id, ResultMethod.WITHDRAWAL, performed_by,
                        f"Opponent withdrew: {reason}")
    else:
        match.status = MatchStatus.CANCELLED
        match.notes = f"Withdrawal with no opponent: {reason}"

    _create_audit(db, division.tournament_id, "withdrawal", "competitor",
                   competitor_id,
                   {"match_id": match.id, "opponent_id": opponent_id},
                   performed_by, reason)

    db.flush()


def handle_no_show(db: Session, match: Match, competitor_id: int,
                    policy: str, reason: str = "No show",
                    performed_by: str = "admin"):
    """Handle a no-show based on tournament policy."""
    division = db.query(Division).get(match.division_id)
    competitor = db.query(Competitor).get(competitor_id)

    if competitor_id not in (match.competitor1_id, match.competitor2_id):
        raise ValueError("Competitor is not in this match.")

    competitor.status = CompetitorStatus.NO_SHOW
    opponent_id = match.competitor2_id if competitor_id == match.competitor1_id else match.competitor1_id

    if policy == "walkover" and opponent_id:
        advance_winner(db, match, opponent_id, ResultMethod.WALKOVER, performed_by,
                        f"No-show: {reason}")
    elif policy == "dq":
        competitor.status = CompetitorStatus.DISQUALIFIED
        if opponent_id:
            advance_winner(db, match, opponent_id, ResultMethod.DQ, performed_by,
                            f"No-show DQ: {reason}")
    elif policy == "reschedule":
        match.status = MatchStatus.QUEUED
        match.notes = f"Rescheduled due to no-show: {reason}"

    _create_audit(db, division.tournament_id, "no_show", "competitor",
                   competitor_id,
                   {"match_id": match.id, "policy": policy},
                   performed_by, reason)

    db.flush()


def handle_substitution(db: Session, match: Match, old_competitor_id: int,
                         new_competitor_data: dict, division: Division,
                         reason: str, performed_by: str = "admin"):
    """Replace a competitor in a match with a new one."""
    tournament = division.tournament

    # Check substitution cutoff
    if match.round_number > tournament.substitution_cutoff_round:
        raise ValueError(
            f"Substitutions not allowed after round {tournament.substitution_cutoff_round}. "
            f"Current round: {match.round_number}."
        )

    if old_competitor_id not in (match.competitor1_id, match.competitor2_id):
        raise ValueError("Competitor to replace is not in this match.")

    # Create new competitor
    new_comp = Competitor(
        division_id=division.id,
        full_name=new_competitor_data["full_name"],
        declared_weight=new_competitor_data.get("declared_weight"),
        gym_team=new_competitor_data.get("gym_team"),
        status=CompetitorStatus.ACTIVE,
    )
    db.add(new_comp)
    db.flush()

    # Replace in match
    if match.competitor1_id == old_competitor_id:
        match.competitor1_id = new_comp.id
    else:
        match.competitor2_id = new_comp.id

    # Mark old competitor
    old_comp = db.query(Competitor).get(old_competitor_id)
    if old_comp:
        old_comp.status = CompetitorStatus.WITHDRAWN

    _create_audit(db, division.tournament_id, "substitution", "competitor",
                   old_competitor_id,
                   {"new_competitor_id": new_comp.id, "match_id": match.id,
                    "new_name": new_comp.full_name},
                   performed_by, reason)

    db.flush()
    return new_comp


def rollback_result(db: Session, match: Match, reason: str,
                     performed_by: str = "admin"):
    """
    Rollback a match result. Clears winner and un-advances from subsequent matches.
    Only safe if no subsequent matches have been played.
    """
    if match.status != MatchStatus.COMPLETED:
        raise ValueError("Can only rollback completed matches.")

    division = db.query(Division).get(match.division_id)

    # Check if the winner has played in the next match
    if match.next_match_id:
        next_match = db.query(Match).get(match.next_match_id)
        if next_match and next_match.status in (MatchStatus.COMPLETED, MatchStatus.IN_PROGRESS):
            raise ValueError(
                "Cannot rollback: the next match is already in progress or completed. "
                "Rollback that match first."
            )
        # Remove advanced competitor from next match
        if next_match:
            if next_match.competitor1_id == match.winner_id:
                next_match.competitor1_id = None
            if next_match.competitor2_id == match.winner_id:
                next_match.competitor2_id = None

    old_winner = match.winner_id
    match.winner_id = None
    match.result_method = None
    match.status = MatchStatus.PENDING
    match.notes = f"Result rolled back: {reason}"

    _create_audit(db, division.tournament_id, "result_rollback", "match",
                   match.id,
                   {"previous_winner_id": old_winner},
                   performed_by, reason)

    db.flush()
    return match


def correct_result(db: Session, match: Match, correct_winner_id: int,
                    result_method: str, reason: str,
                    performed_by: str = "admin"):
    """Correct a match result: rollback then re-advance."""
    # First rollback
    rollback_result(db, match, f"Correction: {reason}", performed_by)

    # Then advance correct winner
    advance_winner(db, match, correct_winner_id, result_method, performed_by,
                    f"Corrected result: {reason}")

    _create_audit(db, match.division.tournament_id, "result_corrected", "match",
                   match.id,
                   {"correct_winner_id": correct_winner_id, "method": result_method},
                   performed_by, reason)

    db.flush()
    return match
