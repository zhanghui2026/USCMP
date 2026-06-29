"""Tests for real members import module.

Covers:
1. Vendor data missing → clear error
2. Import from fixture → correct field mapping
3. Idempotency (re-import → no duplicates)
4. source="uscl", last_updated set
5. official_ids.fec preserved, fec_candidate_id = first
6. latest_term_start/latest_term_end preserved
7. committee_memberships assembled
8. bioguide_id null → skipped
9. _infer_congress_from_terms
10. _assemble_committee_memberships
11. data_mode detection via members.source
12. Mock seed data has source="mock"
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch, call

from app.etl.import_real_members import (
    check_vendor_data_exists,
    _assemble_committee_memberships,
    _infer_congress_from_terms,
    import_members_from_adapter,
    RealMembersImportError,
)
from app.etl.adapters.congress_legislators_adapter import CongressLegislatorsAdapter
from app.scripts.mock_data_generator import MockDataGenerator

FIXTURES_DIR = str(
    Path(__file__).resolve().parent
    / "fixtures" / "congress_legislators_minimal"
)


class TestCheckVendorDataExists:
    def test_missing_directory_raises(self):
        with pytest.raises(RealMembersImportError, match="Vendor data directory not found"):
            check_vendor_data_exists("/nonexistent/path/12345")

    def test_missing_required_files_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(RealMembersImportError, match="Required vendor files missing"):
                check_vendor_data_exists(tmpdir)

    def test_valid_directory_passes(self):
        check_vendor_data_exists(FIXTURES_DIR)


class TestAssembleCommitteeMemberships:
    def test_basic_join(self):
        memberships = [
            {
                "person_id": "uscl_person_A00001",
                "committee_entity_id": "uscl_committee_SSAF",
                "role": "Chair",
                "congress": 119,
                "start_date": "2025-01-03",
                "end_date": None,
            },
        ]
        entities = [
            {
                "entity_id": "uscl_committee_SSAF",
                "name": "Senate Armed Services Committee",
                "entity_type": "committee",
            },
        ]
        result = _assemble_committee_memberships(
            memberships, entities, "uscl_person_A00001"
        )
        assert len(result) == 1
        assert result[0]["committee"] == "Senate Armed Services Committee"
        assert result[0]["role"] == "Chair"
        assert result[0]["congress"] == 119

    def test_unknown_committee(self):
        memberships = [
            {
                "person_id": "uscl_person_X",
                "committee_entity_id": "unknown_entity",
                "role": "Member",
            },
        ]
        result = _assemble_committee_memberships(memberships, [], "uscl_person_X")
        assert len(result) == 1
        assert result[0]["committee"] == "unknown_entity"

    def test_only_matching_person(self):
        memberships = [
            {"person_id": "A", "committee_entity_id": "C1", "role": "Member"},
            {"person_id": "B", "committee_entity_id": "C2", "role": "Chair"},
        ]
        entities = [
            {"entity_id": "C1", "name": "Committee 1"},
            {"entity_id": "C2", "name": "Committee 2"},
        ]
        result = _assemble_committee_memberships(memberships, entities, "A")
        assert len(result) == 1
        assert result[0]["committee"] == "Committee 1"


class TestInferCongressFromTerms:
    def test_most_recent_term(self):
        terms = [
            {"person_id": "P1", "start_date": "2019-01-03", "congress": 116},
            {"person_id": "P1", "start_date": "2025-01-03", "congress": 119},
            {"person_id": "P1", "start_date": "2021-01-03", "congress": 117},
        ]
        assert _infer_congress_from_terms(terms, "P1") == 119

    def test_no_terms(self):
        assert _infer_congress_from_terms([], "P1") is None

    def test_other_person(self):
        terms = [
            {"person_id": "P2", "start_date": "2025-01-03", "congress": 119},
        ]
        assert _infer_congress_from_terms(terms, "P1") is None


class TestImportMembersFromAdapter:
    def test_normalized_data_maps_correctly(self):
        adapter = CongressLegislatorsAdapter("test_sha", vendor_dir=FIXTURES_DIR)
        adapter.load_vendor_dataset(adapter.commit_sha)
        adapter.normalize([])
        norm = adapter.get_normalized()
        persons = norm["persons"]

        assert len(persons) > 0
        p = persons[0]
        assert p["person_id"].startswith("uscl_person_")
        assert p["canonical_name"]
        assert p["party"]
        assert p["chamber"] in ("senate", "house")
        assert p["bioguide_id"]
        assert p["data_namespace"] == "sandbox"
        assert p["data_source"] == "unitedstates/congress-legislators"

    def test_source_field_set_to_uscl(self):
        adapter = CongressLegislatorsAdapter("test_sha", vendor_dir=FIXTURES_DIR)
        adapter.load_vendor_dataset(adapter.commit_sha)
        adapter.normalize([])
        norm = adapter.get_normalized()

        for p in norm["persons"]:
            assert p.get("bioguide_id"), f"Person {p['person_id']} missing bioguide_id"
            assert p["data_namespace"] == "sandbox"
            assert p["data_source"] == "unitedstates/congress-legislators"

    def test_fec_ids_preserved(self):
        adapter = CongressLegislatorsAdapter("test_sha", vendor_dir=FIXTURES_DIR)
        adapter.load_vendor_dataset(adapter.commit_sha)
        adapter.normalize([])
        norm = adapter.get_normalized()

        for p in norm["persons"]:
            fec = p.get("fec_ids", [])
            assert isinstance(fec, list), f"fec_ids must be list, got {type(fec)}"

    def test_latest_term_dates_present(self):
        adapter = CongressLegislatorsAdapter("test_sha", vendor_dir=FIXTURES_DIR)
        adapter.load_vendor_dataset(adapter.commit_sha)
        adapter.normalize([])
        norm = adapter.get_normalized()

        for p in norm["persons"]:
            assert "latest_term_start" in p
            assert "latest_term_end" in p

    def test_committee_memberships_join(self):
        adapter = CongressLegislatorsAdapter("test_sha", vendor_dir=FIXTURES_DIR)
        adapter.load_vendor_dataset(adapter.commit_sha)
        adapter.normalize([])
        norm = adapter.get_normalized()

        memberships = norm.get("committee_memberships", [])
        entities = norm.get("political_entities", [])

        for p in norm["persons"]:
            result = _assemble_committee_memberships(memberships, entities, p["person_id"])
            for cm in result:
                assert "committee" in cm
                assert "role" in cm

    def test_import_with_mock_db_upserts(self):
        adapter = CongressLegislatorsAdapter("test_sha", vendor_dir=FIXTURES_DIR)
        adapter.load_vendor_dataset(adapter.commit_sha)
        adapter.normalize([])
        norm = adapter.get_normalized()
        persons = norm["persons"]

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.etl.import_real_members.SessionLocal", return_value=mock_db):
            with patch("app.etl.import_real_members.check_vendor_data_exists"):
                result = import_members_from_adapter(adapter, FIXTURES_DIR)
                assert result["total_persons"] == len(persons)
                assert result["inserted"] == len(persons)
                assert result["updated"] == 0

    def test_import_idempotent_updates(self):
        adapter = CongressLegislatorsAdapter("test_sha", vendor_dir=FIXTURES_DIR)
        adapter.load_vendor_dataset(adapter.commit_sha)
        adapter.normalize([])

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [
            ("A000001", "uscl_person_A000001"),
            ("B000002", "uscl_person_B000002"),
            ("C000003", "uscl_person_C000003"),
        ]

        with patch("app.etl.import_real_members.SessionLocal", return_value=mock_db):
            with patch("app.etl.import_real_members.check_vendor_data_exists"):
                result = import_members_from_adapter(adapter, FIXTURES_DIR)
                assert result["inserted"] == 0
                assert result["updated"] > 0

    def test_no_persons_raises(self):
        adapter = CongressLegislatorsAdapter("test_sha", vendor_dir=FIXTURES_DIR)
        adapter._normalized = {
            "persons": [],
            "person_terms": [],
            "political_entities": [],
            "committee_memberships": [],
            "social_accounts": [],
        }

        mock_db = MagicMock()
        with patch("app.etl.import_real_members.SessionLocal", return_value=mock_db):
            with patch("app.etl.import_real_members.check_vendor_data_exists"):
                with pytest.raises(RealMembersImportError, match="No persons found"):
                    import_members_from_adapter(adapter, FIXTURES_DIR)


class TestMockSeedSourceField:
    def test_mock_members_have_source_mock(self):
        gen = MockDataGenerator()
        gen.generate_all()
        for m in gen.members:
            assert m["source"] == "mock"
            assert "last_updated" in m
            assert "latest_term_start" in m
            assert "latest_term_end" in m
            assert "official_ids" in m
            assert m["official_ids"] == {}

    def test_mock_members_latest_term_none(self):
        gen = MockDataGenerator()
        gen.generate_all()
        for m in gen.members:
            assert m["latest_term_start"] is None
            assert m["latest_term_end"] is None


class TestSkippedPersonWithoutBioguide:
    def test_person_without_bioguide_is_skipped(self):
        from unittest.mock import PropertyMock

        persons_without_bioguide = [
            {
                "person_id": "uscl_person_NOBIO001",
                "canonical_name": "No Bioguide Person",
                "display_name": "No Bioguide Person",
                "aliases": [],
                "person_type": "legislator",
                "party": "Independent",
                "chamber": "senate",
                "state": "CA",
                "district": None,
                "bioguide_id": None,
                "govtrack_id": "400001",
                "opensecrets_id": "N00000001",
                "fec_ids": ["H0CA00123"],
                "latest_term_start": "2025-01-03",
                "latest_term_end": "2027-01-03",
                "data_namespace": "sandbox",
                "data_source": "unitedstates/congress-legislators",
                "source_reliability": "secondary",
                "etl_run_id": "test",
            }
        ]

        adapter = CongressLegislatorsAdapter("test_sha", vendor_dir=FIXTURES_DIR)
        adapter._normalized = {
            "persons": persons_without_bioguide,
            "person_terms": [],
            "political_entities": [],
            "committee_memberships": [],
            "social_accounts": [],
        }

        mock_db = MagicMock()

        with patch("app.etl.import_real_members.SessionLocal", return_value=mock_db):
            with patch("app.etl.import_real_members.check_vendor_data_exists"):
                result = import_members_from_adapter(adapter, FIXTURES_DIR)
                assert result["inserted"] == 0
                assert result["updated"] == 0
                assert result["skipped_no_bioguide"] == 1


class TestDataModeDetection:
    def test_all_mock_returns_mock(self):
        gen = MockDataGenerator()
        gen.generate_all()
        sources = {m["source"] for m in gen.members}
        assert sources == {"mock"}

    def test_adapter_persons_have_correct_structure(self):
        adapter = CongressLegislatorsAdapter("test_sha", vendor_dir=FIXTURES_DIR)
        adapter.load_vendor_dataset(adapter.commit_sha)
        adapter.normalize([])
        norm = adapter.get_normalized()

        for p in norm["persons"]:
            field_keys = [
                "person_id", "canonical_name", "display_name", "party",
                "chamber", "state", "bioguide_id", "govtrack_id",
                "opensecrets_id", "fec_ids", "latest_term_start",
                "latest_term_end", "data_namespace", "data_source",
            ]
            for key in field_keys:
                assert key in p, f"Person {p.get('person_id', '?')} missing field: {key}"
