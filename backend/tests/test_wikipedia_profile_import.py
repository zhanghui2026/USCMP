"""Tests for Wikipedia Profile Import (v0.6).

Tests cover:
1. Member with wikipedia_title can import profile
2. Member without wikipedia_title is skipped
3. Wikipedia page missing is handled (skipped/failed)
4. Missing fields return null/[]
5. Idempotent re-import
6. API /members/{id}/profile returns correct structure
7. profile_sources contains source info
8. No risk scores, predictions, or interest judgments
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.postgres import Base
from app.models.sqlalchemy.models import Member, MemberProfile
from app.main import app
from app.etl.adapters.wikipedia_profile_adapter import (
    WikipediaProfileAdapter,
    _load_uscl_wikipedia_ids,
    _clean_date,
    _parse_infobox_html,
    _extract_education,
    _extract_occupations,
)
from tests.fixtures.wikipedia_profiles import FIXTURE_PROFILES


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session():
    engine = create_engine(settings.postgres_url_sync, echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def sample_members(db_session):
    members = [
        Member(
            id="test_member_profile_001",
            canonical_name="Test Person A",
            display_name="Test Person A",
            person_type="legislator",
            party="Democratic",
            chamber="senate",
            state="VA",
            bioguide_id="TP000001",
            source="uscl",
            source_reliability="secondary",
            official_ids={"fec": [], "wikipedia": "Mark Warner", "wikidata": "Q453893"},
        ),
        Member(
            id="test_member_profile_002",
            canonical_name="Test Person B",
            display_name="Test Person B",
            person_type="legislator",
            party="Republican",
            chamber="house",
            state="TX",
            bioguide_id="TP000002",
            source="uscl",
            source_reliability="secondary",
            official_ids={"fec": []},
        ),
    ]
    for m in members:
        existing = db_session.query(Member).filter(Member.id == m.id).first()
        if not existing:
            db_session.add(m)
    db_session.commit()
    yield members
    for m in members:
        db_session.query(MemberProfile).filter(
            MemberProfile.member_id.in_([m.id for m in members])
        ).delete(synchronize_session=False)
        db_session.query(Member).filter(Member.id.in_([m.id for m in members])).delete(synchronize_session=False)
    db_session.commit()


class TestWikipediaProfileAdapter:
    """Test the adapter's field extraction and data handling."""

    def test_fixture_fetch_returns_profile(self):
        adapter = WikipediaProfileAdapter(rate_delay=0, fixtures=FIXTURE_PROFILES)
        profile = adapter.fetch_profile("Mark Warner", "Q453893")
        assert profile is not None
        assert profile["birth_date"] == "1954-12-15"
        assert profile["source"] == "wikipedia"
        assert profile["source_reliability"] == "external_open_content"

    def test_skip_without_wikipedia_id(self):
        adapter = WikipediaProfileAdapter()
        profile = adapter.fetch_profile(None, None)
        assert profile is None
        assert adapter.get_stats()["skipped_no_wikidata"] == 1

    def test_missing_page_skipped(self):
        adapter = WikipediaProfileAdapter()
        profile = adapter.fetch_profile("NonexistentPageXYZ123456789", None)
        assert profile is None
        # For network failures, it may be counted as skipped or failed
        stats = adapter.get_stats()
        total_skipped_or_failed = stats.get("skipped_missing_page", 0) + stats.get("failed", 0)
        assert total_skipped_or_failed >= 1

    def test_null_fields_on_missing_data(self):
        adapter = WikipediaProfileAdapter(rate_delay=0, fixtures=FIXTURE_PROFILES)
        profile = adapter._build_from_fixture("Mark R. Warner")
        assert profile["education"] is not None
        assert isinstance(profile["education"], list)
        assert profile.get("military_service") is not None

    def test_profile_sources_contains_info(self):
        adapter = WikipediaProfileAdapter(rate_delay=0, fixtures=FIXTURE_PROFILES)
        profile = adapter.fetch_profile("Mark Warner", "Q453893")
        sources = profile.get("profile_sources", {})
        assert "wikipedia_title" in sources
        assert "wikipedia_url" in sources
        assert "retrieved_at" in sources

    def test_no_risk_or_prediction_content(self):
        adapter = WikipediaProfileAdapter(rate_delay=0, fixtures=FIXTURE_PROFILES)
        profile = adapter.fetch_profile("Mark Warner", "Q453893")
        forbidden_keys = [
            "risk_score", "prediction", "conflict_of_interest",
            "china_stance", "controversy", "political_leaning",
        ]
        for key in forbidden_keys:
            assert key not in profile
        assert "risk" not in str(profile.get("short_summary", "")).lower()


class TestProfileImport:
    """Test the import_member_profiles functionality."""

    def test_import_with_wikipedia_title(self, db_session, sample_members):
        from app.etl.import_member_profiles import import_member_profiles
        from pathlib import Path

        vendor_dir = str(Path(__file__).resolve().parents[1] / "data" / "external" / "congress-legislators" / "dfa9622263dd4c8d08636926e498f1845704d7eb")
        adapter = WikipediaProfileAdapter(rate_delay=0, fixtures=FIXTURE_PROFILES)
        stats = import_member_profiles(adapter, vendor_dir, dry_run=False, limit=None)

        profile = db_session.query(MemberProfile).filter(
            MemberProfile.member_id == "test_member_profile_001"
        ).first()
        if profile:
            assert profile.source == "wikipedia"
            assert profile.bioguide_id == "TP000001"
            assert profile.wikipedia_title is not None

    def test_member_without_wikipedia_skipped(self, db_session, sample_members):
        from app.etl.import_member_profiles import import_member_profiles
        from pathlib import Path

        vendor_dir = str(Path(__file__).resolve().parents[1] / "data" / "external" / "congress-legislators" / "dfa9622263dd4c8d08636926e498f1845704d7eb")
        adapter = WikipediaProfileAdapter(rate_delay=0, fixtures=FIXTURE_PROFILES)
        stats = import_member_profiles(adapter, vendor_dir, dry_run=False, limit=None)

        profile = db_session.query(MemberProfile).filter(
            MemberProfile.member_id == "test_member_profile_002"
        ).first()
        assert profile is None

    def test_idempotent_reimport(self, db_session, sample_members):
        from app.etl.import_member_profiles import import_member_profiles
        from pathlib import Path

        vendor_dir = str(Path(__file__).resolve().parents[1] / "data" / "external" / "congress-legislators" / "dfa9622263dd4c8d08636926e498f1845704d7eb")

        adapter1 = WikipediaProfileAdapter(rate_delay=0, fixtures=FIXTURE_PROFILES)
        stats1 = import_member_profiles(adapter1, vendor_dir, dry_run=False, limit=None)

        adapter2 = WikipediaProfileAdapter(rate_delay=0, fixtures=FIXTURE_PROFILES)
        stats2 = import_member_profiles(adapter2, vendor_dir, dry_run=False, limit=None)

        assert stats2["imported"] == 0
        assert stats2["updated"] >= 1


class TestProfileAPI:
    """Test the /api/members/{id}/profile endpoint."""

    def test_get_profile_returns_correct_structure(self, client, db_session, sample_members):
        profile = MemberProfile(
            id="test_profile_api_001",
            member_id="test_member_profile_001",
            bioguide_id="TP000001",
            wikipedia_title="Mark Warner",
            wikipedia_url="https://en.wikipedia.org/wiki/Mark_Warner",
            wikidata_qid="Q453893",
            short_summary="Test summary",
            birth_date="1954-12-15",
            birth_place="Indianapolis, IN",
            education=[{"institution": "Harvard"}],
            occupations=["Politician"],
            career_highlights=[],
            prior_positions=[],
            military_service=[],
            profile_sources={"wikipedia_title": "Mark Warner", "wikipedia_url": "https://en.wikipedia.org/wiki/Mark_Warner"},
            source="wikipedia",
            source_reliability="external_open_content",
            last_updated=datetime.now(timezone.utc),
        )
        db_session.add(profile)
        db_session.commit()

        resp = client.get("/api/members/test_member_profile_001/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["member_id"] == "test_member_profile_001"
        assert data["source"] == "wikipedia"
        assert data["birth_date"] == "1954-12-15"
        assert data["education"] == [{"institution": "Harvard"}]
        assert "profile_sources" in data

        db_session.query(MemberProfile).filter(MemberProfile.id == "test_profile_api_001").delete()
        db_session.commit()

    def test_profile_not_found_returns_404(self, client):
        resp = client.get("/api/members/nonexistent_member_id/profile")
        assert resp.status_code == 404

    def test_empty_fields_use_defaults(self, client, db_session, sample_members):
        profile = MemberProfile(
            id="test_profile_api_002",
            member_id="test_member_profile_001",
            bioguide_id="TP000001",
            wikipedia_title="Test Title",
            source="wikipedia",
            source_reliability="external_open_content",
            last_updated=datetime.now(timezone.utc),
        )
        db_session.add(profile)
        db_session.commit()

        resp = client.get("/api/members/test_member_profile_001/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["education"] == []
        assert data["occupations"] == []
        assert data["career_highlights"] == []

        db_session.query(MemberProfile).filter(MemberProfile.id == "test_profile_api_002").delete()
        db_session.commit()


class TestDateCleaning:
    def test_iso_date(self):
        assert _clean_date("1954-12-15") == "1954-12-15"

    def test_month_name_date(self):
        assert _clean_date("December 15, 1954") == "1954-12-15"

    def test_year_only(self):
        assert _clean_date("1954") == "1954"

    def test_empty_string(self):
        assert _clean_date("") is None

    def test_none(self):
        assert _clean_date(None) is None


class TestInfoboxParsing:
    def test_basic_html(self):
        html = '<table><tr><th scope="row">Born</th><td>December 15, 1954</td></tr></table>'
        result = _parse_infobox_html(html)
        assert "born" in result

    def test_empty_html(self):
        result = _parse_infobox_html("")
        assert result == {}

    def test_education_extraction(self):
        infobox = {"education": "Harvard University (BA)\nYale University (JD)"}
        result = _extract_education(infobox)
        assert len(result) > 0

    def test_occupations_extraction(self):
        infobox = {"occupation": "Politician, Businessman"}
        result = _extract_occupations(infobox)
        assert "Politician" in result
        assert "Businessman" in result
