"""API integration tests with mocked database dependencies.

Uses FastAPI TestClient with MockDataGenerator data to verify
request/response contracts, error handling, and validation.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.scripts.mock_data_generator import MockDataGenerator


@pytest.fixture(scope="module")
def mock_data():
    gen = MockDataGenerator()
    gen.generate_all()
    return gen


@pytest.fixture(scope="module")
def client(mock_data):
    from app.main import app

    def _mock_get_db():
        db = MagicMock()
        db.query.return_value = db
        db.filter.return_value = db
        db.offset.return_value = db
        db.limit.return_value = db
        db.order_by.return_value = db
        db.all.return_value = []
        db.first.return_value = None
        db.count.return_value = 0
        db.scalar.return_value = 0
        return db

    app.dependency_overrides = {}
    from app.db.postgres import get_db
    app.dependency_overrides[get_db] = _mock_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ── Health ──


class TestHealthAPI:
    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "postgres" in data
        assert "neo4j" in data
        assert "data_mode" in data
        assert "version" in data
        assert "timestamp" in data


# ── Members ──


class TestMembersAPI:
    def test_members_list_returns_200(self, client, mock_data):
        from app.main import app
        from app.db.postgres import get_db
        from app.models.sqlalchemy.models import Member

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db
            db.offset.return_value = db
            db.limit.return_value = db

            mock_members = []
            for m_data in mock_data.members[:10]:
                mock_m = MagicMock(spec=Member)
                for key, val in m_data.items():
                    setattr(mock_m, key, val)
                mock_members.append(mock_m)

            db.all.return_value = mock_members
            db.count.return_value = len(mock_members)
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.get("/api/members")
        assert resp.status_code == 200
        data = resp.json()
        assert "members" in data
        assert "total" in data
        assert data["total"] == 10
        assert len(data["members"]) == 10
        assert "id" in data["members"][0]
        assert "canonical_name" in data["members"][0]
        assert "party" in data["members"][0]

    def test_members_filter_by_chamber(self, client, mock_data):
        from app.main import app
        from app.db.postgres import get_db
        from app.models.sqlalchemy.models import Member

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db
            db.offset.return_value = db
            db.limit.return_value = db

            senate = [m for m in mock_data.members if m["chamber"] == "senate"][:5]
            mock_members = []
            for m_data in senate:
                mock_m = MagicMock(spec=Member)
                for key, val in m_data.items():
                    setattr(mock_m, key, val)
                mock_members.append(mock_m)

            db.all.return_value = mock_members
            db.count.return_value = len(mock_members)
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.get("/api/members?chamber=senate")
        assert resp.status_code == 200
        data = resp.json()
        for m in data["members"]:
            assert m["chamber"] == "senate"

    def test_member_not_found_returns_404(self, client):
        from app.main import app
        from app.db.postgres import get_db

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db
            db.first.return_value = None
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.get("/api/members/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error_code"] == "NOT_FOUND"

    def test_member_detail_returns_200(self, client, mock_data):
        from app.main import app
        from app.db.postgres import get_db
        from app.models.sqlalchemy.models import Member

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db

            m_data = mock_data.members[0]
            mock_m = MagicMock(spec=Member)
            for key, val in m_data.items():
                setattr(mock_m, key, val)
            db.first.return_value = mock_m
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.get(f"/api/members/{mock_data.members[0]['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == mock_data.members[0]["id"]
        assert "canonical_name" in data
        assert "display_name" in data
        assert "party" in data


# ── Search ──


class TestSearchAPI:
    def test_search_returns_200(self, client, mock_data):
        from app.main import app
        from app.db.postgres import get_db
        from app.models.sqlalchemy.models import Member, Organization, Event as EventModelDB

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db
            db.limit.return_value = db

            mock_members = []
            for m_data in mock_data.members[:3]:
                mock_m = MagicMock(spec=Member)
                for key, val in m_data.items():
                    setattr(mock_m, key, val)
                mock_members.append(mock_m)

            def _return_members():
                return mock_members

            def _return_orgs():
                return []

            def _return_events():
                return []

            db.all.side_effect = [_return_members(), _return_orgs(), _return_events()]
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.get("/api/search?query=Defense")
        assert resp.status_code == 200
        data = resp.json()
        assert "members" in data
        assert "organizations" in data
        assert "events" in data
        assert "total_count" in data

    def test_search_too_short_returns_422(self, client):
        # FastAPI validates min_length=2 at the parameter level, returning 422
        resp = client.get("/api/search?query=a")
        assert resp.status_code == 422

    def test_search_whitespace_only_returns_400(self, client):
        # Whitespace query passes min_length but fails the strip check -> 400
        resp = client.get("/api/search?query=++")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error_code"] == "SEARCH_QUERY_TOO_SHORT"

    def test_search_no_results_returns_200(self, client):
        from app.main import app
        from app.db.postgres import get_db

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db
            db.limit.return_value = db
            db.all.side_effect = [[], [], []]
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.get("/api/search?query=xyznonexistent123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 0
        assert len(data["members"]) == 0
        assert len(data["organizations"]) == 0
        assert len(data["events"]) == 0
        assert data["source"] == "postgresql"


# ── Reports ──


class TestReportsAPI:
    def test_report_member_not_found_returns_404(self, client):
        from app.main import app
        from app.db.postgres import get_db

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db
            db.first.return_value = None
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.post("/api/reports/markdown", json={"member_id": "nonexistent"})
        assert resp.status_code == 404
        data = resp.json()
        assert data["error_code"] == "NOT_FOUND"

    def test_report_generates_markdown(self, client, mock_data):
        from app.main import app
        from app.db.postgres import get_db
        from app.models.sqlalchemy.models import Member

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db

            m_data = mock_data.members[0]
            mock_m = MagicMock(spec=Member)
            for key, val in m_data.items():
                setattr(mock_m, key, val)
            db.first.return_value = mock_m
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.post("/api/reports/markdown", json={
            "member_id": mock_data.members[0]["id"],
            "format": "markdown",
            "include_graph": False,
            "include_predictions": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "markdown"
        assert len(data["content"]) > 0
        assert "disclaimer" in data
        assert "Mock" in data["content"] or "mock" in data["content"].lower()


# ── Compare ──


class TestCompareAPI:
    def test_compare_too_few_members_returns_422(self, client):
        # Pydantic validates min_length=2 for member_ids -> 422
        resp = client.post("/api/compare", json={"member_ids": ["single_member"]})
        assert resp.status_code == 422

    def test_compare_missing_members_returns_404(self, client):
        from app.main import app
        from app.db.postgres import get_db

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db
            db.all.return_value = []
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.post("/api/compare", json={
            "member_ids": ["person_nonexistent_1", "person_nonexistent_2"],
        })
        assert resp.status_code == 404
        data = resp.json()
        assert data["error_code"] == "NOT_FOUND"


# ── Prediction ──


class TestPredictionAPI:
    def test_prediction_returns_200_with_mock_data(self, client, mock_data):
        from app.main import app
        from app.db.postgres import get_db
        from app.models.sqlalchemy.models import Member

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db

            m_data = mock_data.members[0]
            mock_m = MagicMock(spec=Member)
            for key, val in m_data.items():
                setattr(mock_m, key, val)
            mock_m.bioguide_id = None
            db.first.return_value = mock_m
            db.all.return_value = []
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.post("/api/predictions/vote", json={
            "member_id": mock_data.members[0]["id"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "predicted_position" in data
        assert "probability" in data
        assert "disclaimer" in data
        assert "Mock" in data.get("disclaimer", "")

    def test_prediction_member_not_found_returns_404(self, client):
        from app.main import app
        from app.db.postgres import get_db

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db
            db.first.return_value = None
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.post("/api/predictions/vote", json={"member_id": "nonexistent"})
        assert resp.status_code == 404
        data = resp.json()
        assert data["error_code"] == "NOT_FOUND"


# ── Data Quality ──


class TestDataQualityAPI:
    def test_data_quality_returns_200(self, client):
        resp = client.get("/api/data-quality/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_nodes" in data
        assert "total_edges" in data
        assert "data_mode" in data
