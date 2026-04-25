"""
API integration tests using FastAPI TestClient.
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
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def staff_token(client):
    resp = client.post("/api/auth/login", json={"password": "staff123", "role": "staff"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestAuth:
    def test_admin_login(self, client):
        resp = client.post("/api/auth/login", json={"password": "admin123", "role": "admin"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_wrong_password(self, client):
        resp = client.post("/api/auth/login", json={"password": "wrong", "role": "admin"})
        assert resp.status_code == 401

    def test_staff_login(self, client):
        resp = client.post("/api/auth/login", json={"password": "staff123", "role": "staff"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "staff"


class TestTournamentCRUD:
    def test_create_tournament(self, client, admin_token):
        resp = client.post("/api/tournaments", json={
            "name": "Test Cup", "date": "2026-05-01", "venue": "Test Arena",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Cup"

    def test_list_tournaments_public(self, client, admin_token):
        client.post("/api/tournaments", json={
            "name": "T1", "date": "2026-05-01", "venue": "V1",
        }, headers=auth_header(admin_token))
        resp = client.get("/api/tournaments")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_create_tournament_requires_admin(self, client):
        resp = client.post("/api/tournaments", json={
            "name": "T", "date": "2026-05-01", "venue": "V",
        })
        assert resp.status_code == 403

    def test_create_tournament_staff_denied(self, client, staff_token):
        resp = client.post("/api/tournaments", json={
            "name": "T", "date": "2026-05-01", "venue": "V",
        }, headers=auth_header(staff_token))
        assert resp.status_code == 403


class TestDivisionCRUD:
    def _create_tournament(self, client, token):
        resp = client.post("/api/tournaments", json={
            "name": "T1", "date": "2026-05-01", "venue": "V1",
        }, headers=auth_header(token))
        return resp.json()["id"]

    def test_create_division(self, client, admin_token):
        tid = self._create_tournament(client, admin_token)
        resp = client.post(f"/api/tournaments/{tid}/divisions", json={
            "name": "Lightweight", "weight_class_min": 57, "weight_class_max": 70,
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Lightweight"

    def test_list_divisions_public(self, client, admin_token):
        tid = self._create_tournament(client, admin_token)
        client.post(f"/api/tournaments/{tid}/divisions", json={
            "name": "LW",
        }, headers=auth_header(admin_token))
        resp = client.get(f"/api/tournaments/{tid}/divisions")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestCompetitorCRUD:
    def _setup(self, client, token):
        tid = client.post("/api/tournaments", json={
            "name": "T1", "date": "2026-05-01", "venue": "V1",
        }, headers=auth_header(token)).json()["id"]
        did = client.post(f"/api/tournaments/{tid}/divisions", json={
            "name": "LW",
        }, headers=auth_header(token)).json()["id"]
        return tid, did

    def test_add_competitor(self, client, admin_token):
        tid, did = self._setup(client, admin_token)
        resp = client.post(f"/api/tournaments/{tid}/divisions/{did}/competitors", json={
            "full_name": "John Doe", "declared_weight": 68.5,
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "John Doe"

    def test_duplicate_warning(self, client, admin_token):
        tid, did = self._setup(client, admin_token)
        client.post(f"/api/tournaments/{tid}/divisions/{did}/competitors", json={
            "full_name": "John Doe", "gym_team": "Alpha",
        }, headers=auth_header(admin_token))
        resp = client.post(f"/api/tournaments/{tid}/divisions/{did}/competitors", json={
            "full_name": "John Doe", "gym_team": "Alpha",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 409
        assert "duplicate" in resp.json()["detail"].lower()

    def test_force_duplicate(self, client, admin_token):
        tid, did = self._setup(client, admin_token)
        client.post(f"/api/tournaments/{tid}/divisions/{did}/competitors", json={
            "full_name": "John Doe", "gym_team": "Alpha",
        }, headers=auth_header(admin_token))
        resp = client.post(f"/api/tournaments/{tid}/divisions/{did}/competitors?force=true", json={
            "full_name": "John Doe", "gym_team": "Alpha",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200

    def test_bulk_add(self, client, admin_token):
        tid, did = self._setup(client, admin_token)
        resp = client.post(f"/api/tournaments/{tid}/divisions/{did}/competitors/bulk", json={
            "competitors": [
                {"full_name": "Fighter 1"},
                {"full_name": "Fighter 2"},
                {"full_name": "Fighter 3"},
            ]
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 3


class TestBracketAPI:
    def _setup_with_competitors(self, client, token, count=4):
        tid = client.post("/api/tournaments", json={
            "name": "T1", "date": "2026-05-01", "venue": "V1",
        }, headers=auth_header(token)).json()["id"]
        did = client.post(f"/api/tournaments/{tid}/divisions", json={
            "name": "LW",
        }, headers=auth_header(token)).json()["id"]
        for i in range(count):
            client.post(f"/api/tournaments/{tid}/divisions/{did}/competitors", json={
                "full_name": f"Fighter {i+1}",
                "gym_team": f"Gym {i % 2}",
            }, headers=auth_header(token))
        return tid, did

    def test_generate_bracket(self, client, admin_token):
        tid, did = self._setup_with_competitors(client, admin_token, 4)
        resp = client.post(f"/api/tournaments/{tid}/divisions/{did}/bracket", json={
            "seeding": "random",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_get_bracket_public(self, client, admin_token):
        tid, did = self._setup_with_competitors(client, admin_token, 4)
        client.post(f"/api/tournaments/{tid}/divisions/{did}/bracket", json={
            "seeding": "random",
        }, headers=auth_header(admin_token))
        resp = client.get(f"/api/tournaments/{tid}/divisions/{did}/bracket")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_record_result(self, client, admin_token):
        tid, did = self._setup_with_competitors(client, admin_token, 4)
        bracket = client.post(f"/api/tournaments/{tid}/divisions/{did}/bracket", json={
            "seeding": "random",
        }, headers=auth_header(admin_token)).json()

        # Find a non-bye R1 match
        match = next(m for m in bracket if m["round_number"] == 1 and not m["is_bye"]
                     and m["competitor1_id"] and m["competitor2_id"])

        resp = client.post(
            f"/api/tournaments/{tid}/divisions/{did}/matches/{match['id']}/result",
            json={"winner_id": match["competitor1_id"], "result_method": "decision"},
            headers=auth_header(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["winner_id"] == match["competitor1_id"]

    def test_staff_can_record_result(self, client, admin_token, staff_token):
        tid, did = self._setup_with_competitors(client, admin_token, 4)
        bracket = client.post(f"/api/tournaments/{tid}/divisions/{did}/bracket", json={
            "seeding": "random",
        }, headers=auth_header(admin_token)).json()

        match = next(m for m in bracket if m["round_number"] == 1 and not m["is_bye"]
                     and m["competitor1_id"] and m["competitor2_id"])

        resp = client.post(
            f"/api/tournaments/{tid}/divisions/{did}/matches/{match['id']}/result",
            json={"winner_id": match["competitor1_id"], "result_method": "ko"},
            headers=auth_header(staff_token),
        )
        assert resp.status_code == 200


class TestPublicReadOnly:
    def test_public_cannot_create(self, client):
        resp = client.post("/api/tournaments", json={
            "name": "T", "date": "2026-05-01", "venue": "V",
        })
        assert resp.status_code == 403

    def test_public_can_read(self, client, admin_token):
        client.post("/api/tournaments", json={
            "name": "T1", "date": "2026-05-01", "venue": "V1",
        }, headers=auth_header(admin_token))
        resp = client.get("/api/tournaments")
        assert resp.status_code == 200


class TestTournamentSettings:
    def _create_tournament(self, client, token):
        resp = client.post("/api/tournaments", json={
            "name": "T1", "date": "2026-05-01", "venue": "V1",
        }, headers=auth_header(token))
        return resp.json()["id"]

    def test_registration_open_defaults_false(self, client, admin_token):
        tid = self._create_tournament(client, admin_token)
        resp = client.get(f"/api/tournaments/{tid}")
        assert resp.json()["registration_open"] is False

    def test_admin_can_open_registration(self, client, admin_token):
        tid = self._create_tournament(client, admin_token)
        resp = client.put(f"/api/tournaments/{tid}",
                          json={"registration_open": True},
                          headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.json()["registration_open"] is True

    def test_admin_can_close_registration(self, client, admin_token):
        tid = client.post("/api/tournaments", json={
            "name": "T1", "date": "2026-05-01", "venue": "V1",
            "registration_open": True,
        }, headers=auth_header(admin_token)).json()["id"]

        resp = client.put(f"/api/tournaments/{tid}",
                          json={"registration_open": False},
                          headers=auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.json()["registration_open"] is False

    def test_setting_persists_after_reload(self, client, admin_token):
        tid = self._create_tournament(client, admin_token)
        client.put(f"/api/tournaments/{tid}",
                   json={"registration_open": True},
                   headers=auth_header(admin_token))
        resp = client.get(f"/api/tournaments/{tid}")
        assert resp.json()["registration_open"] is True

    def test_update_settings_requires_admin(self, client, admin_token, staff_token):
        tid = self._create_tournament(client, admin_token)

        resp = client.put(f"/api/tournaments/{tid}",
                          json={"registration_open": True})
        assert resp.status_code == 403

        resp = client.put(f"/api/tournaments/{tid}",
                          json={"registration_open": True},
                          headers=auth_header(staff_token))
        assert resp.status_code == 403

    def test_update_multiple_settings(self, client, admin_token):
        tid = self._create_tournament(client, admin_token)
        resp = client.put(f"/api/tournaments/{tid}", json={
            "registration_open": True,
            "name": "Updated Cup",
            "num_rings": 3,
            "no_show_policy": "dq",
        }, headers=auth_header(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["registration_open"] is True
        assert data["name"] == "Updated Cup"
        assert data["num_rings"] == 3
        assert data["no_show_policy"] == "dq"


class TestHealthCheck:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "mode" in data
