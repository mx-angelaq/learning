"""
Tests for the self-registration feature:
- Successful submission (happy path)
- Validation failures (missing/invalid fields)
- Duplicate prevention
- Registration when closed
- Admin approval creates competitor
- Admin rejection
- Status check by email
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    resp = client.post("/api/auth/login", json={"password": "admin123", "role": "admin"})
    return resp.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _create_tournament(client, token, registration_open=True):
    """Helper: create a tournament with registration open."""
    resp = client.post("/api/tournaments", json={
        "name": "Test Cup", "date": "2026-05-01", "venue": "Test Arena",
        "registration_open": registration_open,
    }, headers=auth_header(token))
    return resp.json()["id"]


def _create_division(client, token, tid):
    """Helper: create a division."""
    resp = client.post(f"/api/tournaments/{tid}/divisions", json={
        "name": "Lightweight", "weight_class_min": 57, "weight_class_max": 70,
    }, headers=auth_header(token))
    return resp.json()["id"]


def _valid_registration(division_id):
    return {
        "full_name": "Jane Fighter",
        "email": "jane@example.com",
        "division_id": division_id,
        "declared_weight": 68.5,
        "gym_team": "Iron Fist MMA",
        "waiver_agreed": True,
    }


class TestRegistrationSubmission:
    """Public registration submission - happy path."""

    def test_successful_registration(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations",
                           json=_valid_registration(did))
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Jane Fighter"
        assert data["email"] == "jane@example.com"
        assert data["status"] == "pending"
        assert data["division_name"] == "Lightweight"
        assert data["id"] is not None

    def test_registration_with_minimal_fields(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations", json={
            "full_name": "Min Fighter",
            "email": "min@example.com",
            "division_id": did,
            "waiver_agreed": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["declared_weight"] is None
        assert data["gym_team"] is None

    def test_registration_with_all_fields(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations", json={
            "full_name": "Full Fighter",
            "email": "full@example.com",
            "division_id": did,
            "declared_weight": 69.0,
            "gym_team": "Power Gym",
            "phone": "+1234567890",
            "age": 25,
            "experience_level": "intermediate",
            "waiver_agreed": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["age"] == 25
        assert data["experience_level"] == "intermediate"


class TestRegistrationValidation:
    """Validation failures - missing/invalid fields."""

    def test_missing_name(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations", json={
            "full_name": "",
            "email": "test@example.com",
            "division_id": did,
            "waiver_agreed": True,
        })
        assert resp.status_code == 422

    def test_invalid_email(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations", json={
            "full_name": "Test",
            "email": "not-an-email",
            "division_id": did,
            "waiver_agreed": True,
        })
        assert resp.status_code == 422

    def test_waiver_not_agreed(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations", json={
            "full_name": "Test Fighter",
            "email": "test@example.com",
            "division_id": did,
            "waiver_agreed": False,
        })
        assert resp.status_code == 400
        assert "waiver" in resp.json()["detail"].lower()

    def test_invalid_division(self, client, admin_token):
        tid = _create_tournament(client, admin_token)

        resp = client.post(f"/api/tournaments/{tid}/registrations", json={
            "full_name": "Test Fighter",
            "email": "test@example.com",
            "division_id": 99999,
            "waiver_agreed": True,
        })
        assert resp.status_code == 400
        assert "division" in resp.json()["detail"].lower()

    def test_nonexistent_tournament(self, client):
        resp = client.post("/api/tournaments/99999/registrations", json={
            "full_name": "Test",
            "email": "test@example.com",
            "division_id": 1,
            "waiver_agreed": True,
        })
        assert resp.status_code == 404


class TestRegistrationClosed:
    """Registration when tournament registration is closed."""

    def test_registration_closed(self, client, admin_token):
        tid = _create_tournament(client, admin_token, registration_open=False)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations",
                           json=_valid_registration(did))
        assert resp.status_code == 400
        assert "not currently open" in resp.json()["detail"].lower()


class TestDuplicatePrevention:
    """Duplicate registration prevention by email."""

    def test_duplicate_email_same_tournament(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        reg = _valid_registration(did)
        resp1 = client.post(f"/api/tournaments/{tid}/registrations", json=reg)
        assert resp1.status_code == 200

        resp2 = client.post(f"/api/tournaments/{tid}/registrations", json=reg)
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"].lower()

    def test_same_email_different_tournament(self, client, admin_token):
        """Same email can register for different tournaments."""
        tid1 = _create_tournament(client, admin_token)
        did1 = _create_division(client, admin_token, tid1)
        tid2 = _create_tournament(client, admin_token)
        did2 = _create_division(client, admin_token, tid2)

        reg1 = _valid_registration(did1)
        reg2 = _valid_registration(did2)

        resp1 = client.post(f"/api/tournaments/{tid1}/registrations", json=reg1)
        assert resp1.status_code == 200

        resp2 = client.post(f"/api/tournaments/{tid2}/registrations", json=reg2)
        assert resp2.status_code == 200

    def test_rejected_can_resubmit(self, client, admin_token):
        """After rejection, the same email can register again."""
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)
        reg = _valid_registration(did)

        # Submit
        resp = client.post(f"/api/tournaments/{tid}/registrations", json=reg)
        reg_id = resp.json()["id"]

        # Reject
        client.post(
            f"/api/tournaments/{tid}/registrations/{reg_id}/review",
            json={"action": "reject", "admin_notes": "Weight class wrong"},
            headers=auth_header(admin_token),
        )

        # Resubmit
        resp2 = client.post(f"/api/tournaments/{tid}/registrations", json=reg)
        assert resp2.status_code == 200


class TestAdminApproval:
    """Admin approval flow creates competitor correctly."""

    def test_approve_creates_competitor(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)
        reg = _valid_registration(did)

        # Submit
        resp = client.post(f"/api/tournaments/{tid}/registrations", json=reg)
        reg_id = resp.json()["id"]

        # Approve
        resp = client.post(
            f"/api/tournaments/{tid}/registrations/{reg_id}/review",
            json={"action": "approve", "admin_notes": "Looks good"},
            headers=auth_header(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["competitor_id"] is not None

        # Verify competitor exists in division
        comps = client.get(f"/api/tournaments/{tid}/divisions/{did}/competitors").json()
        names = [c["full_name"] for c in comps]
        assert "Jane Fighter" in names

        # Verify the competitor has correct data
        comp = next(c for c in comps if c["full_name"] == "Jane Fighter")
        assert comp["email"] == "jane@example.com"
        assert comp["declared_weight"] == 68.5
        assert comp["gym_team"] == "Iron Fist MMA"
        assert comp["status"] == "active"

    def test_reject_registration(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations",
                           json=_valid_registration(did))
        reg_id = resp.json()["id"]

        resp = client.post(
            f"/api/tournaments/{tid}/registrations/{reg_id}/review",
            json={"action": "reject", "admin_notes": "Overweight"},
            headers=auth_header(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        assert resp.json()["admin_notes"] == "Overweight"

        # No competitor created
        comps = client.get(f"/api/tournaments/{tid}/divisions/{did}/competitors").json()
        assert len(comps) == 0

    def test_cannot_review_non_pending(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations",
                           json=_valid_registration(did))
        reg_id = resp.json()["id"]

        # Approve first
        client.post(
            f"/api/tournaments/{tid}/registrations/{reg_id}/review",
            json={"action": "approve"},
            headers=auth_header(admin_token),
        )

        # Try to approve again
        resp = client.post(
            f"/api/tournaments/{tid}/registrations/{reg_id}/review",
            json={"action": "approve"},
            headers=auth_header(admin_token),
        )
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()

    def test_approval_requires_admin(self, client, admin_token):
        """Staff and public cannot approve registrations."""
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations",
                           json=_valid_registration(did))
        reg_id = resp.json()["id"]

        # No auth
        resp = client.post(
            f"/api/tournaments/{tid}/registrations/{reg_id}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 403

        # Staff auth
        staff_resp = client.post("/api/auth/login", json={"password": "staff123", "role": "staff"})
        staff_token = staff_resp.json()["access_token"]
        resp = client.post(
            f"/api/tournaments/{tid}/registrations/{reg_id}/review",
            json={"action": "approve"},
            headers=auth_header(staff_token),
        )
        assert resp.status_code == 403

    def test_approval_logged_in_audit(self, client, admin_token):
        """Approval creates an audit log entry."""
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        resp = client.post(f"/api/tournaments/{tid}/registrations",
                           json=_valid_registration(did))
        reg_id = resp.json()["id"]

        client.post(
            f"/api/tournaments/{tid}/registrations/{reg_id}/review",
            json={"action": "approve"},
            headers=auth_header(admin_token),
        )

        audit = client.get(f"/api/tournaments/{tid}/audit",
                           headers=auth_header(admin_token)).json()
        actions = [a["action"] for a in audit]
        assert "registration_approved" in actions


class TestStatusCheck:
    """Public status check by email."""

    def test_check_status(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        client.post(f"/api/tournaments/{tid}/registrations",
                    json=_valid_registration(did))

        resp = client.get(f"/api/tournaments/{tid}/registrations/check?email=jane@example.com")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"
        assert resp.json()["full_name"] == "Jane Fighter"

    def test_check_status_not_found(self, client, admin_token):
        tid = _create_tournament(client, admin_token)

        resp = client.get(f"/api/tournaments/{tid}/registrations/check?email=nobody@example.com")
        assert resp.status_code == 404

    def test_email_normalized(self, client, admin_token):
        """Email is lowercased on submission, check also normalizes."""
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        reg = _valid_registration(did)
        reg["email"] = "Jane@Example.COM"
        client.post(f"/api/tournaments/{tid}/registrations", json=reg)

        resp = client.get(f"/api/tournaments/{tid}/registrations/check?email=JANE@example.com")
        assert resp.status_code == 200


class TestAdminListRegistrations:
    """Admin listing and filtering registrations."""

    def test_list_pending(self, client, admin_token):
        tid = _create_tournament(client, admin_token)
        did = _create_division(client, admin_token, tid)

        # Add two registrations
        for i in range(2):
            reg = _valid_registration(did)
            reg["email"] = f"fighter{i}@example.com"
            reg["full_name"] = f"Fighter {i}"
            client.post(f"/api/tournaments/{tid}/registrations", json=reg)

        resp = client.get(f"/api/tournaments/{tid}/registrations?status=pending",
                          headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_requires_admin(self, client, admin_token):
        tid = _create_tournament(client, admin_token)

        resp = client.get(f"/api/tournaments/{tid}/registrations")
        assert resp.status_code == 403
