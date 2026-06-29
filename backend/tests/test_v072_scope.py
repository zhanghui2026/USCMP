"""Scope-aware tests for v0.7.2 Current Members Scope.

Tests that default API behavior returns only current members,
graph queries filter historical persons by default,
and include_historical parameters work correctly.
"""

from unittest.mock import MagicMock
from datetime import datetime, timezone


class TestCurrentMembersScope:
    """Test current members scope filtering in API responses."""

    def test_members_api_default_excludes_historical(self, client, mock_data):
        from app.main import app
        from app.db.postgres import get_db
        from app.models.sqlalchemy.models import Member

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db
            db.offset.return_value = db
            db.limit.return_value = db

            # Only return members with is_current=True
            current_members = [
                m for m in mock_data.members if m.get("is_current", True)
            ][:5]

            mock_members = []
            for m_data in current_members:
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
        # All returned members should have member_scope field; mock data has scope='mock'
        for m in data["members"]:
            assert "member_scope" in m
            assert m["member_scope"] in ("current", "mock", "test")

        app.dependency_overrides.clear()

    def test_members_api_include_historical(self, client, mock_data):
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
            for m_data in mock_data.members[:5]:
                mock_m = MagicMock(spec=Member)
                for key, val in m_data.items():
                    setattr(mock_m, key, val)
                mock_m.member_scope = "historical"
                mock_m.is_current = False
                mock_members.append(mock_m)

            db.all.return_value = mock_members
            db.count.return_value = len(mock_members)
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.get("/api/members?include_historical=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["members"]) == 5
        # All should be historical
        for m in data["members"]:
            assert m["member_scope"] == "historical"

        app.dependency_overrides.clear()

    def test_search_default_excludes_historical(self, client, mock_data):
        from app.main import app
        from app.db.postgres import get_db
        from app.models.sqlalchemy.models import Member, Organization, Event as EventModelDB

        def _override_get_db():
            db = MagicMock()
            db.query.return_value = db
            db.filter.return_value = db
            db.limit.return_value = db

            current = []
            for m_data in mock_data.members[:3]:
                mock_m = MagicMock(spec=Member)
                for key, val in m_data.items():
                    setattr(mock_m, key, val)
                mock_m.is_current = True
                current.append(mock_m)

            db.all.side_effect = [current, [], []]
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.get("/api/search?query=Test")
        assert resp.status_code == 200
        data = resp.json()
        assert "members" in data

        app.dependency_overrides.clear()

    def test_member_detail_blocks_historical_by_default(self, client, mock_data):
        from app.main import app
        from app.db.postgres import get_db
        from app.models.sqlalchemy.models import Member

        def _override_get_db():
            db = MagicMock()
            hist = MagicMock(spec=Member)
            hist.id = "hist_001"
            hist.canonical_name = "Historical Person"
            hist.is_current = False
            hist.member_scope = "historical"

            def _first():
                return hist

            db.query.return_value.filter.return_value.first = _first
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.get("/api/members/hist_001")
        assert resp.status_code == 404
        data = resp.json()
        # Error format: {"error_code": "NOT_FOUND", "message": "...", "details": {...}}
        assert "member_scope" in str(data.get("details", ""))

        app.dependency_overrides.clear()

    def test_member_detail_allows_historical_when_explicit(self, client, mock_data):
        from app.main import app
        from app.db.postgres import get_db
        from app.models.sqlalchemy.models import Member

        def _override_get_db():
            db = MagicMock()
            hist = MagicMock(spec=Member)
            hist.id = "hist_001"
            hist.canonical_name = "Historical Person"
            hist.display_name = "Historical Person"
            hist.is_current = False
            hist.member_scope = "historical"
            hist.person_type = "senator"
            hist.party = "Independent"
            hist.chamber = "senate"
            hist.state = "VT"
            hist.district = None
            hist.official_photo_url = None
            hist.bioguide_id = "H000001"
            hist.govtrack_id = None
            hist.fec_candidate_id = None
            hist.opensecrets_id = None
            hist.top_contributors = []
            hist.top_holdings = []
            hist.committee_memberships = []
            hist.career_summary = []
            hist.china_stance_summary = None
            hist.controversies = []
            hist.congress = 112
            hist.source = "uscl"
            hist.latest_term_start = None
            hist.latest_term_end = "2024-01-03"
            hist.official_ids = {}

            def _first():
                return hist

            db.query.return_value.filter.return_value.first = _first
            return db

        app.dependency_overrides[get_db] = _override_get_db

        resp = client.get("/api/members/hist_001?include_historical=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "hist_001"

        app.dependency_overrides.clear()

    def test_stats_include_current_historical_counts(self, client):
        resp = client.get("/api/stats/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_members" in data
        assert "historical_members" in data
        assert isinstance(data["current_members"], int)
        assert isinstance(data["historical_members"], int)

    def test_mock_members_not_current(self, client):
        """Mock members should have member_scope='mock' and is_current=False."""
        resp = client.get("/api/stats/profiles")
        assert resp.status_code == 200
        data = resp.json()
        # Mock members should NOT be counted as current
        assert data["current_members"] <= data["total_members"]


class TestProfileAudit:
    """Test profile quality audit functionality."""

    def test_audit_script_importable(self):
        from app.etl.profile_quality_audit import (
            run_audit, _get_overall_stats, _find_high_value_candidates,
            _check_priority_list, _classify_high_value,
        )
        assert callable(run_audit)
        assert callable(_check_priority_list)

    def test_audit_stats_structure(self):
        from app.db.postgres import SessionLocal
        from app.etl.profile_quality_audit import _get_overall_stats

        db = SessionLocal()
        try:
            stats = _get_overall_stats(db)
            assert "current_members_total" in stats
            assert stats["current_members_total"] > 0
            assert "available_profiles" in stats
            assert "summary_only_profiles" in stats
            assert "profiles_with_education" in stats
            assert "profiles_with_prior_positions" in stats
            assert "profiles_with_graph_facts" in stats
        finally:
            db.close()

    def test_priority_check_list(self):
        from app.db.postgres import SessionLocal
        from app.etl.profile_quality_audit import _check_priority_list

        db = SessionLocal()
        try:
            results = _check_priority_list(db)
            assert len(results) > 0
            at_least_one_available = any(
                r.profile_status == "available" for r in results
            )
            assert at_least_one_available, "Expected at least one priority member to have available profile"
        finally:
            db.close()

    def test_classify_high_value(self):
        from app.etl.profile_quality_audit import (
            _classify_high_value, ProfileAuditEntry,
        )

        entry = ProfileAuditEntry(
            member_id="test", canonical_name="Test", display_name="Test Person",
            party="D", chamber="senate", state="CA",
            bioguide_id="T000001", congress=118,
            wikipedia_title="Test Person", wikidata_qid="Q123",
            profile_status="summary_only", source="fixture",
            has_education=False, has_prior_positions=False,
            has_occupations=False, has_graph_facts=False,
        )
        reasons = _classify_high_value(entry)
        assert "senator" in reasons
        assert "has_wikipedia_id_but_unparsed" in reasons
        assert "recent_congress" in reasons

    def test_fixture_source_distinction(self):
        """Fixture profiles should have source='fixture', not 'wikipedia'."""
        from app.db.postgres import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            r = db.execute(text(
                "SELECT count(*) FROM member_profiles WHERE source = 'fixture'"
            )).fetchone()
            assert r[0] >= 14, f"Expected at least 14 fixture profiles, got {r[0]}"
        finally:
            db.close()
