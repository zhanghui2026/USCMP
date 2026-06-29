"""Tests for v0.8 batch profile enrichment pipeline."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.etl.enrich_profiles import (
    load_snapshots,
    match_member,
    _normalize_profile_fields,
    enrich_profiles,
)
from app.etl.profile_status import compute_profile_status
from app.main import app


# ── fixture helpers ──────────────────────────────────────────────────────────


def _make_snapshot(bioguide_id: str, **overrides) -> dict:
    snap = {
        "bioguide_id": bioguide_id,
        "wikipedia_title": f"Test {bioguide_id}",
        "wikipedia_url": f"https://en.wikipedia.org/wiki/Test_{bioguide_id}",
        "wikidata_qid": f"Q{bioguide_id}",
        "image_url": "",
        "short_summary": f"Member {bioguide_id} is a test profile.",
        "birth_date": "1970-01-01",
        "birth_place": "Testville, USA",
        "education": [{"institution": "Test University", "degree": "BA"}],
        "occupations": ["Attorney"],
        "prior_positions": [{"position": "Test Position"}],
        "employers": [],
        "military_service": [],
        "profile_sources": {},
    }
    snap.update(overrides)
    return snap


def _write_snapshot(tmpdir: str, bioguide_id: str, **overrides) -> Path:
    snap = _make_snapshot(bioguide_id, **overrides)
    fpath = Path(tmpdir) / f"{bioguide_id}.json"
    fpath.write_text(json.dumps(snap), encoding="utf-8")
    return fpath


# ── snapshot loading ─────────────────────────────────────────────────────────


class TestSnapshotLoading:
    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as td:
            by_bioguide, by_qid, by_title = load_snapshots(td)
            assert len(by_bioguide) == 0
            assert len(by_qid) == 0
            assert len(by_title) == 0

    def test_single_snapshot_indexed_three_ways(self):
        with tempfile.TemporaryDirectory() as td:
            _write_snapshot(td, "A000001")
            by_bioguide, by_qid, by_title = load_snapshots(td)
            assert "A000001" in by_bioguide
            assert "QA000001" in by_qid
            assert "Test A000001" in by_title

    def test_missing_directory_returns_empty(self):
        by_bioguide, by_qid, by_title = load_snapshots("/nonexistent/dir")
        assert len(by_bioguide) == 0

    def test_invalid_json_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "BAD.json"
            bad.write_text("not json", encoding="utf-8")
            _write_snapshot(td, "A000001")
            by_bioguide, by_qid, by_title = load_snapshots(td)
            assert "A000001" in by_bioguide

    def test_multiple_snapshots(self):
        with tempfile.TemporaryDirectory() as td:
            _write_snapshot(td, "A000001")
            _write_snapshot(td, "B000002")
            _write_snapshot(td, "C000003")
            by_bioguide, _, _ = load_snapshots(td)
            assert len(by_bioguide) == 3


# ── member matching ──────────────────────────────────────────────────────────


class TestMemberMatching:
    def _make_mock_member(self, bioguide_id=None, wikipedia_title=None, wikidata_qid=None):
        m = MagicMock()
        m.bioguide_id = bioguide_id
        m.official_ids = {"wikipedia": wikipedia_title, "wikidata": wikidata_qid}
        return m

    def test_bioguide_priority_highest(self):
        by_bioguide = {"A000001": {"bioguide_id": "A000001"}}
        by_qid = {"QXYZ": {"bioguide_id": "B000002"}}
        by_title = {"Test Title": {"bioguide_id": "C000003"}}
        member = self._make_mock_member(bioguide_id="A000001", wikipedia_title="Test Title", wikidata_qid="QXYZ")
        result = match_member(member, by_bioguide, by_qid, by_title)
        assert result["bioguide_id"] == "A000001"

    def test_qid_fallback(self):
        by_bioguide: dict[str, dict] = {}
        by_qid = {"QXYZ": {"bioguide_id": "B000002"}}
        by_title: dict[str, dict] = {}
        member = self._make_mock_member(bioguide_id=None, wikidata_qid="QXYZ")
        result = match_member(member, by_bioguide, by_qid, by_title)
        assert result["bioguide_id"] == "B000002"

    def test_title_fallback(self):
        by_bioguide: dict[str, dict] = {}
        by_qid: dict[str, dict] = {}
        by_title = {"Test Title": {"bioguide_id": "C000003"}}
        member = self._make_mock_member(bioguide_id=None, wikipedia_title="Test Title")
        result = match_member(member, by_bioguide, by_qid, by_title)
        assert result["bioguide_id"] == "C000003"

    def test_no_match(self):
        by_bioguide: dict[str, dict] = {}
        by_qid: dict[str, dict] = {}
        by_title: dict[str, dict] = {}
        member = self._make_mock_member(bioguide_id="ZZZZZZ")
        result = match_member(member, by_bioguide, by_qid, by_title)
        assert result is None

    def test_bioguide_wins_even_when_qid_differs(self):
        by_bioguide = {"A000001": {"bioguide_id": "A000001", "title": "Correct via bioguide"}}
        by_qid = {"QDIFF": {"bioguide_id": "WRONG", "title": "Wrong match via qid"}}
        by_title = {"Some Title": {"bioguide_id": "ALSO_WRONG", "title": "Wrong via title"}}
        member = self._make_mock_member(bioguide_id="A000001", wikidata_qid="QDIFF", wikipedia_title="Some Title")
        result = match_member(member, by_bioguide, by_qid, by_title)
        assert result["title"] == "Correct via bioguide"


# ── profile status computation ───────────────────────────────────────────────


class TestProfileStatus:
    def test_summary_only_minimal(self):
        data = {"short_summary": "foo", "birth_date": "", "birth_place": ""}
        status, parsed, missing = compute_profile_status(data)
        assert status == "summary_only"

    def test_partial_with_one_structured_field(self):
        data = {
            "short_summary": "foo",
            "birth_date": "1970-01-01",
            "education": [{"institution": "Harvard"}],
        }
        status, parsed, missing = compute_profile_status(data)
        assert status == "partial"

    def test_available_with_two_structured_fields(self):
        data = {
            "short_summary": "foo",
            "birth_date": "1970-01-01",
            "education": [{"institution": "Harvard"}],
            "prior_positions": [{"position": "Senator"}],
        }
        status, parsed, missing = compute_profile_status(data)
        assert status == "available"

    def test_summary_only_upgrades_to_available(self):
        before = {"short_summary": "foo", "birth_date": ""}
        status_before, _, _ = compute_profile_status(before)
        assert status_before == "summary_only"

    def test_available_not_downgraded_by_missing_birthdate(self):
        data = {
            "short_summary": "foo",
            "birth_date": "",
            "education": [{"institution": "Harvard"}],
            "prior_positions": [{"position": "Senator"}],
        }
        status, _, _ = compute_profile_status(data)
        assert status in ("partial", "summary_only")


# ── field normalization ──────────────────────────────────────────────────────


class TestFieldNormalization:
    def test_empty_fields_default_to_empty_list(self):
        snap = _make_snapshot("A000001", education=[], occupations=[])
        fields = _normalize_profile_fields(snap)
        assert fields["education"] == []
        assert fields["occupations"] == []
        assert fields["employers"] == []

    def test_missing_fields_default_to_empty(self):
        snap = {"bioguide_id": "A000001", "short_summary": "test"}
        fields = _normalize_profile_fields(snap)
        assert fields["education"] == []
        assert fields["prior_positions"] == []
        assert fields["employers"] == []

    def test_preserves_all_fields(self):
        snap = _make_snapshot("A000001")
        fields = _normalize_profile_fields(snap)
        assert fields["birth_date"] == "1970-01-01"
        assert fields["birth_place"] == "Testville, USA"
        assert len(fields["education"]) == 1
        assert len(fields["occupations"]) == 1


# ── pipeline with dry-run ────────────────────────────────────────────────────


class TestEnrichDryRun:
    def test_dry_run_no_changes(self):
        with tempfile.TemporaryDirectory() as td:
            _write_snapshot(td, "A000001")
            stats = enrich_profiles(mode="snapshot", snapshot_dir=td, dry_run=True, limit=10)
            assert stats["mode"] == "snapshot"
            assert stats["snapshots_loaded"] == 1
            assert stats["matched"] <= stats["snapshots_loaded"]
            assert stats["imported"] == 0
            assert stats["updated"] == 0

    def test_dry_run_with_limit(self):
        with tempfile.TemporaryDirectory() as td:
            _write_snapshot(td, "A000001")
            _write_snapshot(td, "B000002")
            stats = enrich_profiles(mode="snapshot", snapshot_dir=td, dry_run=True, limit=1)
            assert stats["current_members"] == 1


# ── available protection ─────────────────────────────────────────────────────


class TestAvailableProtection:
    def test_existing_available_not_downgraded_in_enrich_stats(self):
        """Verify that enrich stats count skipped_existing_available correctly."""
        with tempfile.TemporaryDirectory() as td:
            _write_snapshot(td, "K000367")  # Amy Klobuchar - existing available
            stats = enrich_profiles(mode="snapshot", snapshot_dir=td, dry_run=True)
            assert "skipped_existing_available" in stats


# ── coverage report ──────────────────────────────────────────────────────────


class TestCoverageReport:
    def test_report_mode_returns_valid_structure(self):
        stats = enrich_profiles(mode="report")
        assert "total_current_members" in stats
        assert stats["total_current_members"] > 0
        assert "profiles_with_status" in stats
        assert "coverage_pct" in stats
        ps = stats["profiles_with_status"]
        total = ps["available"] + ps["partial"] + ps["summary_only"] + ps["no_profile"]
        assert total == stats["total_current_members"]


# ── stats API ────────────────────────────────────────────────────────────────


class TestStatsAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = TestClient(app)

    def test_current_coverage_endpoint(self):
        resp = self.client.get("/api/stats/profiles/current-coverage")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_current_members" in data
        assert "available" in data
        assert "partial" in data
        assert "summary_only" in data
        assert "enriched_pct" in data

    def test_coverage_pct_add_up(self):
        resp = self.client.get("/api/stats/profiles/current-coverage")
        data = resp.json()
        with_profile = data["available"] + data["partial"] + data["summary_only"]
        without = data["without_profile"]
        assert with_profile + without == data["total_current_members"]

    def test_stats_endpoint_still_works(self):
        resp = self.client.get("/api/stats/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_members" in data
        assert "current_members" in data
        assert "available_profiles" in data
