"""Test that claims and relationships have proper evidence."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scripts.mock_data_generator import MockDataGenerator


class TestEvidenceRequired:
    def setup_method(self):
        self.gen = MockDataGenerator()
        self.gen.generate_all()

    def test_all_relations_have_claims(self):
        main_rels = [
            r for r in self.gen.relationships
            if r["type"] not in ("HAS_CLAIM", "EVIDENCED_BY")
        ]
        for r in main_rels:
            assert r.get("claim_id"), f"Relation {r['id']} missing claim_id"
            claim = next((c for c in self.gen.claims if c["claim_id"] == r["claim_id"]), None)
            assert claim is not None, f"Claim {r['claim_id']} not found for relation {r['id']}"

    def test_claims_have_evidence(self):
        for claim in self.gen.claims:
            evidence_rels = [
                r for r in self.gen.relationships
                if r["type"] == "EVIDENCED_BY" and r["source_id"] == claim["claim_id"]
            ]
            assert len(evidence_rels) > 0, f"Claim {claim['claim_id']} has no evidence"

    def test_low_confidence_marked(self):
        low_conf_claims = [c for c in self.gen.claims if c["confidence_score"] < 0.5]
        for c in low_conf_claims:
            assert c["review_status"] == "needs_review", (
                f"Low confidence claim {c['claim_id']} not marked needs_review"
            )

    def test_source_docs_exist(self):
        doc_ids = {d["id"] for d in self.gen.source_docs}
        evidence_rels = [r for r in self.gen.relationships if r["type"] == "EVIDENCED_BY"]
        for r in evidence_rels:
            assert r["target_id"] in doc_ids, (
                f"Evidence points to non-existent doc {r['target_id']}"
            )
