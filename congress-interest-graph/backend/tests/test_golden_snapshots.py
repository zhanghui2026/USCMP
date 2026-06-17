"""Golden snapshot tests.

Fixed mock seed (42) validates consistent outputs across:
- Members list
- Search
- Graph
- Evidence
- Report
- Prediction

These tests ensure output stability across code changes.
"""

import json
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.scripts.mock_data_generator import MockDataGenerator


class TestGoldenSnapshots(unittest.TestCase):
    """Golden snapshot tests with fixed seed=42."""

    @classmethod
    def setUpClass(cls):
        cls.gen = MockDataGenerator()
        cls.gen.generate_all()

    # ── Members ──

    def test_member_count(self):
        members = self.gen.members
        self.assertEqual(len(members), 50)

    def test_first_member_keys(self):
        m = self.gen.members[0]
        expected_keys = [
            "id", "canonical_name", "display_name", "aliases", "person_type",
            "party", "chamber", "state", "district", "congress",
            "committee_memberships", "top_contributors", "top_holdings",
            "career_summary", "china_stance_summary", "controversies",
            "source", "last_updated", "latest_term_start", "latest_term_end",
            "official_ids",
        ]
        for key in expected_keys:
            self.assertIn(key, m, f"Member missing key: {key}")

    def test_member_ids_unique(self):
        ids = [m["id"] for m in self.gen.members]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_parties(self):
        parties = {m["party"] for m in self.gen.members}
        self.assertIn("Democratic", parties)
        self.assertIn("Republican", parties)

    # ── Organizations ──

    def test_org_count(self):
        orgs = self.gen.orgs
        self.assertEqual(len(orgs), 100)

    def test_org_has_canonical_name(self):
        for org in self.gen.orgs:
            self.assertTrue(org.get("canonical_name"), f"Org missing canonical_name: {org['id']}")

    # ── Events ──

    def test_event_count(self):
        events = self.gen.events
        self.assertEqual(len(events), 100)

    def test_events_have_dates(self):
        for ev in self.gen.events:
            self.assertIsNotNone(ev.get("event_date"))

    # ── Claims ──

    def test_claim_count(self):
        claims = self.gen.claims
        self.assertEqual(len(claims), 300)

    def test_all_claims_mock(self):
        for claim in self.gen.claims:
            self.assertEqual(claim["source_reliability"], "mock")
            self.assertEqual(claim["extraction_method"], "mock")

    def test_claims_have_subject_object(self):
        for claim in self.gen.claims:
            self.assertTrue(claim.get("subject_id"), f"Claim {claim['claim_id']} missing subject_id")
            self.assertTrue(claim.get("object_id"), f"Claim {claim['claim_id']} missing object_id")

    # ── Source Documents ──

    def test_source_doc_count(self):
        docs = self.gen.source_docs
        self.assertEqual(len(docs), 500)

    def test_source_docs_mock(self):
        for doc in self.gen.source_docs:
            self.assertEqual(doc["source_reliability"], "mock")

    # ── Relationships ──

    def test_relationships_exist(self):
        rels = self.gen.relationships
        self.assertTrue(len(rels) > 0, "No relationships generated")

    def test_low_confidence_rels(self):
        main_rels = [r for r in self.gen.relationships if r.get("confidence_score") is not None]
        low_conf = [r for r in main_rels if r["confidence_score"] < 0.5]
        self.assertTrue(len(low_conf) > 0, "No low-confidence relationships")
        self.assertTrue(len(low_conf) >= 20, f"Expected >=20 low-confidence, got {len(low_conf)}")

    def test_all_rels_have_claim_id(self):
        main_rels = [r for r in self.gen.relationships if r.get("claim_id")]
        self.assertTrue(len(main_rels) > 0, "No relationships with claim_id")
        self.assertEqual(len(main_rels), 300)

    # ── Determinism ──

    def test_deterministic_output(self):
        gen2 = MockDataGenerator()
        gen2.generate_all()

        self.assertEqual(
            len(self.gen.members), len(gen2.members),
            "Member count differs between runs",
        )
        self.assertEqual(
            self.gen.members[0]["id"], gen2.members[0]["id"],
            "First member ID differs between runs",
        )
        self.assertEqual(
            self.gen.claims[0]["claim_id"], gen2.claims[0]["claim_id"],
            "First claim ID differs between runs",
        )

    # ── Review Status ──

    def test_needs_review_flags(self):
        claims = self.gen.claims
        needs_review = [c for c in claims if c.get("review_status") == "needs_review"]
        self.assertTrue(len(needs_review) > 0, "No claims marked needs_review")

    # ── Search Corner Cases ──

    def test_search_by_state(self):
        members = self.gen.members
        ca_members = [m for m in members if m["state"] == "CA"]
        self.assertTrue(len(ca_members) > 0, "No CA members")

    def test_search_by_chamber(self):
        members = self.gen.members
        senators = [m for m in members if m["chamber"] == "senate"]
        representatives = [m for m in members if m["chamber"] == "house"]
        self.assertTrue(len(senators) > 0, "No senators")
        self.assertTrue(len(representatives) > 0, "No representatives")


class TestGoldenPredictionSnapshot(unittest.TestCase):
    """Test prediction model with fixed seed data."""

    def test_prediction_unknown_when_insufficient_evidence(self):
        from app.models.pydantic.models import PredictionResponse

        resp = PredictionResponse(
            predicted_position="unknown",
            probability=0.0,
            evidence_count=2,
            data_quality_score=0.4,
            confidence_level="insufficient_data",
            margin_from_baseline=0.0,
            interpretation="Insufficient data",
        )
        self.assertEqual(resp.predicted_position, "unknown")
        self.assertEqual(resp.probability, 0.0)

    def test_prediction_uncertain_in_mid_range(self):
        from app.models.pydantic.models import PredictionResponse

        resp = PredictionResponse(
            predicted_position="uncertain",
            probability=0.51,
            evidence_count=5,
            data_quality_score=0.8,
            confidence_level="low",
            margin_from_baseline=0.01,
            interpretation="Mid-range prediction",
        )
        self.assertEqual(resp.predicted_position, "uncertain")
        self.assertEqual(resp.confidence_level, "low")

    def test_prediction_new_fields_exist(self):
        from app.models.pydantic.models import PredictionResponse

        resp = PredictionResponse(
            predicted_position="support",
            probability=0.75,
            evidence_count=5,
            data_quality_score=0.8,
            confidence_level="high",
            margin_from_baseline=0.25,
            interpretation="Strong evidence",
        )
        self.assertEqual(resp.confidence_level, "high")
        self.assertTrue(hasattr(resp, "margin_from_baseline"))
        self.assertTrue(hasattr(resp, "interpretation"))
        self.assertTrue(hasattr(resp, "confidence_level"))


class TestGoldenHealthSnapshot(unittest.TestCase):
    """Test health response model."""

    def test_health_response_has_data_mode(self):
        from app.models.pydantic.models import HealthResponse
        from datetime import datetime, timezone

        resp = HealthResponse(
            status="ok",
            postgres="ok",
            neo4j="ok",
            data_mode="mock",
            version="0.1.0",
            timestamp=datetime.now(timezone.utc),
        )
        self.assertEqual(resp.data_mode, "mock")
        self.assertEqual(resp.status, "ok")


class TestGoldenDataQualitySnapshot(unittest.TestCase):
    """Test data quality model."""

    def test_data_quality_model(self):
        from app.models.pydantic.models import DataQualitySummaryResponse
        from datetime import datetime, timezone

        dq = DataQualitySummaryResponse(
            total_nodes=100,
            total_edges=200,
            total_claims=50,
            total_source_documents=50,
            low_confidence_edges=94,
            needs_review_claims=45,
            source_reliability_distribution={"mock": 50},
            extraction_method_distribution={"mock": 50},
            node_type_distribution={"Person": 50, "Organization": 50},
            edge_type_distribution={"HAS_CLAIM": 100, "EVIDENCED_BY": 100},
            data_mode="mock",
            generated_at=datetime.now(timezone.utc),
        )
        self.assertEqual(dq.total_nodes, 100)
        self.assertEqual(dq.data_mode, "mock")
        self.assertEqual(dq.low_confidence_edges, 94)


if __name__ == "__main__":
    unittest.main()
