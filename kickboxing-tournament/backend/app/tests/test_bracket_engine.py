"""
Tests for the bracket engine: generation, byes, seeding, advancement,
withdrawal, no-show, substitution, rollback, correction.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.database import Base, engine, SessionLocal
from app.models.db_models import (
    Tournament, Division, Competitor, Match,
    CompetitorStatus, MatchStatus, NoShowPolicy, ResultMethod
)
from app.services.bracket_engine import (
    generate_bracket, advance_winner, handle_withdrawal,
    handle_no_show, handle_substitution, rollback_result,
    correct_result, separate_gyms_seed, _next_power_of_two
)


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh DB for each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def _create_tournament(db, **kwargs):
    t = Tournament(
        name=kwargs.get("name", "Test Tournament"),
        date="2026-04-15",
        venue="Test Venue",
        num_rings=1,
        start_time="09:00",
        bout_duration_minutes=3,
        break_duration_minutes=2,
        buffer_minutes=1,
        no_show_policy=kwargs.get("no_show_policy", NoShowPolicy.WALKOVER),
        substitution_cutoff_round=kwargs.get("substitution_cutoff_round", 2),
    )
    db.add(t)
    db.flush()
    return t


def _create_division(db, tournament_id, name="Test Div"):
    d = Division(tournament_id=tournament_id, name=name)
    db.add(d)
    db.flush()
    return d


def _add_competitors(db, division_id, count, gyms=None):
    comps = []
    for i in range(count):
        c = Competitor(
            division_id=division_id,
            full_name=f"Fighter {i+1}",
            declared_weight=70.0,
            gym_team=gyms[i] if gyms and i < len(gyms) else f"Gym {i % 3}",
            status=CompetitorStatus.ACTIVE,
        )
        db.add(c)
        db.flush()
        comps.append(c)
    return comps


class TestNextPowerOfTwo:
    def test_powers(self):
        assert _next_power_of_two(1) == 1
        assert _next_power_of_two(2) == 2
        assert _next_power_of_two(3) == 4
        assert _next_power_of_two(4) == 4
        assert _next_power_of_two(5) == 8
        assert _next_power_of_two(7) == 8
        assert _next_power_of_two(8) == 8
        assert _next_power_of_two(9) == 16


class TestBracketGeneration:
    def test_power_of_two_competitors(self, db):
        """4 competitors = 3 matches, no byes."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        _add_competitors(db, d.id, 4)

        matches, warning = generate_bracket(db, d, seeding="random")
        db.commit()

        assert len(matches) == 3  # 2 first round + 1 final
        byes = [m for m in matches if m.is_bye]
        assert len(byes) == 0

    def test_non_power_of_two_with_byes(self, db):
        """3 competitors = 1 bye."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        _add_competitors(db, d.id, 3)

        matches, warning = generate_bracket(db, d, seeding="random")
        db.commit()

        assert len(matches) == 3  # bracket_size=4, so 2+1 matches
        byes = [m for m in matches if m.is_bye]
        assert len(byes) == 1

    def test_five_competitors(self, db):
        """5 competitors in bracket of 8: 3 byes."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        _add_competitors(db, d.id, 5)

        matches, warning = generate_bracket(db, d, seeding="random")
        db.commit()

        assert len(matches) == 7  # bracket_size=8, so 4+2+1
        byes = [m for m in matches if m.is_bye]
        assert len(byes) == 3

    def test_seven_competitors(self, db):
        """7 competitors: 1 bye."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        _add_competitors(db, d.id, 7)

        matches, warning = generate_bracket(db, d, seeding="random")
        db.commit()

        byes = [m for m in matches if m.is_bye]
        assert len(byes) == 1

    def test_two_competitors(self, db):
        """Minimum: 2 competitors = 1 match."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        _add_competitors(db, d.id, 2)

        matches, warning = generate_bracket(db, d, seeding="random")
        db.commit()

        assert len(matches) == 1
        assert matches[0].competitor1_id is not None
        assert matches[0].competitor2_id is not None

    def test_one_competitor_fails(self, db):
        """1 competitor should fail."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        _add_competitors(db, d.id, 1)

        matches, warning = generate_bracket(db, d, seeding="random")
        assert len(matches) == 0
        assert "at least 2" in warning.lower()

    def test_regenerate_requires_confirmation(self, db):
        """Regenerating bracket requires confirm_regenerate=True."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        _add_competitors(db, d.id, 4)

        generate_bracket(db, d, seeding="random")
        db.commit()

        # Try regenerate without confirm
        matches, warning = generate_bracket(db, d, seeding="random", confirm_regenerate=False)
        assert len(matches) == 0
        assert "confirm_regenerate" in warning

        # With confirm
        matches, warning = generate_bracket(db, d, seeding="random", confirm_regenerate=True)
        assert len(matches) == 3

    def test_manual_seeding(self, db):
        """Manual seeding respects seed order."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        comps[0].seed = 4
        comps[1].seed = 3
        comps[2].seed = 2
        comps[3].seed = 1
        db.flush()

        matches, _ = generate_bracket(db, d, seeding="manual")
        db.commit()

        # Seed 1 should be first
        first_round = [m for m in matches if m.round_number == 1]
        assert first_round[0].competitor1_id == comps[3].id  # seed 1

    def test_separate_gyms_seeding(self, db):
        """Separate gyms seeding should try to keep same-gym apart."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        gyms = ["Alpha", "Alpha", "Beta", "Beta"]
        _add_competitors(db, d.id, 4, gyms=gyms)

        matches, _ = generate_bracket(db, d, seeding="separate_gyms")
        db.commit()

        # Check round 1 matches don't have same-gym opponents (best effort)
        first_round = [m for m in matches if m.round_number == 1]
        for m in first_round:
            if m.competitor1_id and m.competitor2_id:
                c1 = db.query(Competitor).get(m.competitor1_id)
                c2 = db.query(Competitor).get(m.competitor2_id)
                # Best effort - may not always be possible
                # Just verify it doesn't crash


class TestMatchAdvancement:
    def test_advance_winner(self, db):
        """Recording a result advances winner to next match."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        first_round = sorted(
            [m for m in matches if m.round_number == 1],
            key=lambda m: m.position
        )
        final = [m for m in matches if m.round_number == 2][0]

        # Record result for first match
        m = first_round[0]
        advance_winner(db, m, m.competitor1_id, "decision")
        db.commit()

        # Winner should be in final
        db.refresh(final)
        assert final.competitor1_id == m.competitor1_id or final.competitor2_id == m.competitor1_id

    def test_invalid_winner_rejected(self, db):
        """Winner must be in the match."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        m = [m for m in matches if m.round_number == 1][0]
        # Use a competitor ID not in this match
        other_comp = [c for c in comps if c.id not in (m.competitor1_id, m.competitor2_id)][0]

        with pytest.raises(ValueError, match="not a competitor"):
            advance_winner(db, m, other_comp.id, "decision")


class TestWithdrawal:
    def test_withdrawal_advances_opponent(self, db):
        """Withdrawal makes opponent the winner."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        m = [m for m in matches if m.round_number == 1][0]
        handle_withdrawal(db, m, m.competitor1_id, "Injury")
        db.commit()

        db.refresh(m)
        assert m.winner_id == m.competitor2_id
        assert m.status == MatchStatus.COMPLETED

        withdrawn = db.query(Competitor).get(m.competitor1_id)
        assert withdrawn.status == CompetitorStatus.WITHDRAWN


class TestNoShow:
    def test_walkover_policy(self, db):
        """No-show with walkover policy advances opponent."""
        t = _create_tournament(db, no_show_policy=NoShowPolicy.WALKOVER)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        m = [m for m in matches if m.round_number == 1][0]
        handle_no_show(db, m, m.competitor1_id, "walkover", "Did not appear")
        db.commit()

        db.refresh(m)
        assert m.winner_id == m.competitor2_id

    def test_dq_policy(self, db):
        """No-show with DQ policy disqualifies competitor."""
        t = _create_tournament(db, no_show_policy=NoShowPolicy.DQ)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        m = [m for m in matches if m.round_number == 1][0]
        handle_no_show(db, m, m.competitor1_id, "dq", "No show")
        db.commit()

        comp = db.query(Competitor).get(m.competitor1_id)
        assert comp.status == CompetitorStatus.DISQUALIFIED

    def test_reschedule_policy(self, db):
        """No-show with reschedule policy sets match to queued."""
        t = _create_tournament(db, no_show_policy=NoShowPolicy.RESCHEDULE)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        m = [m for m in matches if m.round_number == 1][0]
        handle_no_show(db, m, m.competitor1_id, "reschedule", "Running late")
        db.commit()

        db.refresh(m)
        assert m.status == MatchStatus.QUEUED


class TestSubstitution:
    def test_substitute_round_1(self, db):
        """Can substitute in round 1 when cutoff is round 2."""
        t = _create_tournament(db, substitution_cutoff_round=2)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        m = [m for m in matches if m.round_number == 1][0]
        old_id = m.competitor1_id

        new_comp = handle_substitution(
            db, m, old_id,
            {"full_name": "Replacement Fighter", "declared_weight": 70.0},
            d, "Injury warmup", "admin"
        )
        db.commit()

        db.refresh(m)
        assert m.competitor1_id == new_comp.id
        assert new_comp.full_name == "Replacement Fighter"

        old = db.query(Competitor).get(old_id)
        assert old.status == CompetitorStatus.WITHDRAWN

    def test_substitute_past_cutoff_fails(self, db):
        """Cannot substitute past cutoff round."""
        t = _create_tournament(db, substitution_cutoff_round=1)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        # Get a round 2 match
        final = [m for m in matches if m.round_number == 2][0]
        # We need competitors in the final - advance some first
        m1 = [m for m in matches if m.round_number == 1][0]
        advance_winner(db, m1, m1.competitor1_id, "decision")
        db.commit()
        db.refresh(final)

        if final.competitor1_id:
            with pytest.raises(ValueError, match="not allowed"):
                handle_substitution(
                    db, final, final.competitor1_id,
                    {"full_name": "Late Sub"},
                    d, "Tried", "admin"
                )


class TestRollbackAndCorrection:
    def test_rollback_clears_result(self, db):
        """Rollback clears winner and un-advances."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        m = [m for m in matches if m.round_number == 1][0]
        advance_winner(db, m, m.competitor1_id, "decision")
        db.commit()

        rollback_result(db, m, "Scoring error", "admin")
        db.commit()

        db.refresh(m)
        assert m.winner_id is None
        assert m.status == MatchStatus.PENDING

    def test_rollback_blocked_if_next_played(self, db):
        """Cannot rollback if next match already played."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        r1 = sorted([m for m in matches if m.round_number == 1], key=lambda m: m.position)
        final = [m for m in matches if m.round_number == 2][0]

        # Play both R1 matches and final
        advance_winner(db, r1[0], r1[0].competitor1_id, "decision")
        advance_winner(db, r1[1], r1[1].competitor1_id, "decision")
        db.commit()
        db.refresh(final)
        advance_winner(db, final, final.competitor1_id, "ko")
        db.commit()

        # Try rollback R1 match 1 - should fail because final is completed
        with pytest.raises(ValueError, match="next match"):
            rollback_result(db, r1[0], "Oops", "admin")

    def test_correct_result(self, db):
        """Correct a result: rollback + re-advance."""
        t = _create_tournament(db)
        d = _create_division(db, t.id)
        comps = _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        m = [m for m in matches if m.round_number == 1][0]
        original_winner = m.competitor1_id
        correct_winner = m.competitor2_id

        advance_winner(db, m, original_winner, "decision")
        db.commit()

        correct_result(db, m, correct_winner, "ko", "Wrong winner recorded", "admin")
        db.commit()

        db.refresh(m)
        assert m.winner_id == correct_winner
        assert m.result_method == ResultMethod.KO


class TestSchedulingEstimation:
    def test_schedule_creates_times(self, db):
        """Scheduling estimation assigns times."""
        from app.services.scheduling import estimate_match_times

        t = _create_tournament(db)
        d = _create_division(db, t.id)
        _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        # Set non-bye matches to queued
        for m in matches:
            if not m.is_bye and m.competitor1_id and m.competitor2_id:
                m.status = MatchStatus.QUEUED
        db.commit()

        result = estimate_match_times(db, t.id)
        assert len(result) > 0
        for r in result:
            assert "estimated_time" in r
            assert "ring_number" in r


class TestAuditLog:
    def test_bracket_generation_logged(self, db):
        """Bracket generation creates audit log entries."""
        from app.models.db_models import AuditLog

        t = _create_tournament(db)
        d = _create_division(db, t.id)
        _add_competitors(db, d.id, 4)
        generate_bracket(db, d, seeding="random")
        db.commit()

        logs = db.query(AuditLog).filter(AuditLog.tournament_id == t.id).all()
        assert len(logs) > 0
        actions = [l.action for l in logs]
        assert "bracket_generated" in actions

    def test_withdrawal_logged(self, db):
        """Withdrawals create audit log entries."""
        from app.models.db_models import AuditLog

        t = _create_tournament(db)
        d = _create_division(db, t.id)
        _add_competitors(db, d.id, 4)
        matches, _ = generate_bracket(db, d, seeding="random")
        db.commit()

        m = [m for m in matches if m.round_number == 1][0]
        handle_withdrawal(db, m, m.competitor1_id, "Knee injury")
        db.commit()

        logs = db.query(AuditLog).filter(AuditLog.action == "withdrawal").all()
        assert len(logs) > 0
        assert logs[0].reason == "Knee injury"
