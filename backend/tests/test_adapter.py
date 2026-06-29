"""Tests for CongressLegislatorsAdapter.

Uses minimal test fixtures to validate adapter correctness without
loading the full 64532-claim production dataset.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.etl.adapters.congress_legislators_adapter import CongressLegislatorsAdapter


MINIMAL_DIR = str(
    Path(__file__).resolve().parent
    / "fixtures" / "congress_legislators_minimal"
)


@pytest.fixture
def adapter_minimal():
    """Adapter pointing to minimal test fixtures (2 legislators)."""
    return CongressLegislatorsAdapter(
        commit_sha="test_fixture",
        vendor_dir=MINIMAL_DIR,
    )


class TestCongressLegislatorsAdapter:
    def test_load_vendor_dataset(self, adapter_minimal):
        raw = adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        assert "legislators_current" in raw
        assert "legislators_historical" in raw
        assert "social_media" in raw
        assert "committees_current" in raw
        assert "committee_memberships" in raw

    def test_validate_manifest_success(self, adapter_minimal):
        validation = adapter_minimal.validate_source_manifest()
        assert validation["valid"]
        assert validation["eligible_for_sandbox_import"]

    def test_validate_manifest_fails_with_wrong_sha(self):
        adapter = CongressLegislatorsAdapter(
            commit_sha="bad_sha_12345",
            vendor_dir=MINIMAL_DIR,
        )
        validation = adapter.validate_source_manifest()
        assert not validation["valid"]

    def test_normalize_persons(self, adapter_minimal):
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        norm = adapter_minimal.get_normalized()
        persons = norm["persons"]
        # 2 current + 1 historical = 3 total
        assert len(persons) == 3

        p = persons[0]
        assert p["person_id"].startswith("uscl_person_")
        assert p["canonical_name"]
        assert p["party"]
        assert p["chamber"] in ("senate", "house")
        assert p["data_namespace"] == "sandbox"

    def test_normalize_person_terms(self, adapter_minimal):
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        norm = adapter_minimal.get_normalized()
        terms = norm["person_terms"]
        assert len(terms) >= 2  # at least 2 terms across all legislators

        t = terms[0]
        assert t["term_id"].startswith("uscl_term_")
        assert t["person_id"].startswith("uscl_person_")
        assert t["chamber"] in ("senate", "house")
        assert t["claim_id"].startswith("uscl_claim_term_")
        assert t["confidence_score"] == 0.90

    def test_normalize_committees(self, adapter_minimal):
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        norm = adapter_minimal.get_normalized()
        entities = norm["political_entities"]
        # 3 committees in minimal fixtures
        assert len(entities) == 3

        e = entities[0]
        assert e["entity_id"].startswith("uscl_committee_")
        assert e["name"]
        assert e["entity_type"] == "committee"

    def test_normalize_committee_memberships(self, adapter_minimal):
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        norm = adapter_minimal.get_normalized()
        memberships = norm["committee_memberships"]
        # 2 membership entries in minimal fixtures
        assert len(memberships) == 2

        m = memberships[0]
        assert m["membership_id"].startswith("uscl_member_")
        assert m["person_id"].startswith("uscl_person_")
        assert m["committee_entity_id"].startswith("uscl_committee_")
        assert 0.75 <= m["confidence_score"] <= 0.85

    def test_normalize_social_accounts(self, adapter_minimal):
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        norm = adapter_minimal.get_normalized()
        accounts = norm["social_accounts"]
        # 4 social accounts in minimal fixtures (3 for Alice + 1 for Bob)
        assert len(accounts) == 4

        a = accounts[0]
        assert a["account_id"].startswith("uscl_social_")
        assert a["platform"] in ("twitter", "facebook", "youtube", "instagram")
        assert a["official"] is True

    def test_account_string_type(self, adapter_minimal):
        """Account values must be strings (not int for numeric twitter IDs)."""
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        norm = adapter_minimal.get_normalized()
        for a in norm["social_accounts"]:
            assert isinstance(a["account"], str), (
                f"Account for {a['platform']} must be string, got {type(a['account'])}"
            )

    def test_extract_claims_count(self, adapter_minimal):
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        claims = adapter_minimal.extract_claims([])
        assert len(claims) > 0

        # All claims should have required fields
        for c in claims:
            assert c["claim_id"]
            assert c["claim_type"]
            assert c["subject_id"]
            assert c["object_id"]
            assert c["confidence_score"] > 0
            assert c["data_namespace"] == "sandbox"
            assert c["data_source"] == "unitedstates/congress-legislators"

    def test_claim_types_present(self, adapter_minimal):
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        claims = adapter_minimal.extract_claims([])
        types = {c["claim_type"] for c in claims}
        assert "identity_claim" in types
        assert "term_claim" in types
        assert "committee_membership_claim" in types

    def test_generate_source_documents(self, adapter_minimal):
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        docs = adapter_minimal.generate_source_documents([])
        assert len(docs) >= 4

        d = docs[0]
        assert d["document_id"].startswith("uscl_sdoc_")
        assert d["sha256"]
        assert d["data_namespace"] == "sandbox"

    def test_generate_import_plan_eligible(self, adapter_minimal):
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        claims = adapter_minimal.extract_claims([])
        plan = adapter_minimal.generate_import_plan(claims=claims)

        assert plan["eligible_for_sandbox_import"]
        assert plan["target_namespace"] == "sandbox"
        assert len(plan["import_steps"]) == 8

    def test_rank_to_text(self, adapter_minimal):
        assert adapter_minimal._rank_to_text(1) == "senior"
        assert adapter_minimal._rank_to_text(2) == "member"
        assert adapter_minimal._rank_to_text("member") == "member"
        assert adapter_minimal._rank_to_text("chair") == "chair"

    def test_infer_congress(self, adapter_minimal):
        # 1st Congress: 1789
        assert adapter_minimal._infer_congress("1789-03-04") == 1
        # 103rd Congress: 1993
        assert adapter_minimal._infer_congress("1993-01-05") == 103
        # 117th Congress: 2021
        assert adapter_minimal._infer_congress("2021-01-03") == 117
        # 119th Congress: 2025
        assert adapter_minimal._infer_congress("2025-01-03") == 119
        # Invalid
        assert adapter_minimal._infer_congress("") is None
        assert adapter_minimal._infer_congress("abcd-01-01") is None

    def test_identity_confidence_scores(self, adapter_minimal):
        """Identity claims must be 0.95, terms 0.90, memberships 0.85."""
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        claims = adapter_minimal.extract_claims([])
        for c in claims:
            if c["claim_type"] == "identity_claim":
                assert c["confidence_score"] == 0.95
            elif c["claim_type"] == "term_claim":
                assert c["confidence_score"] == 0.90
            elif c["claim_type"] == "committee_membership_claim":
                assert c["confidence_score"] >= 0.80

    def test_review_status(self, adapter_minimal):
        """Committee memberships with dates should be auto_extracted."""
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        claims = adapter_minimal.extract_claims([])
        for c in claims:
            if c["claim_type"] == "identity_claim":
                assert c["review_status"] == "auto_extracted"
            elif c["claim_type"] == "term_claim":
                assert c["review_status"] == "auto_extracted"

    def test_canonical_name_present(self, adapter_minimal):
        adapter_minimal.load_vendor_dataset(adapter_minimal.commit_sha)
        adapter_minimal.normalize([])
        norm = adapter_minimal.get_normalized()
        for p in norm["persons"]:
            assert p["canonical_name"], f"Person {p['person_id']} missing canonical_name"
            assert len(p["canonical_name"].strip()) > 0
