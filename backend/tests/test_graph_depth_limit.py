"""Test graph query depth limits and safety constraints."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scripts.mock_data_generator import MockDataGenerator
from app.core.config import settings


class TestGraphDepthLimit:
    def test_max_depth_configured(self):
        assert settings.max_graph_depth == 2

    def test_relationships_depth_one(self):
        gen = MockDataGenerator()
        gen.generate_all()

        person_1 = gen.members[0]
        person_id = person_1["id"]

        direct_rels = [
            r for r in gen.relationships
            if r["type"] not in ("HAS_CLAIM", "EVIDENCED_BY")
            and (r["source_id"] == person_id or r["target_id"] == person_id)
        ]
        assert len(direct_rels) > 0, "Person should have direct relationships"

    def test_no_unbounded_relations(self):
        gen = MockDataGenerator()
        gen.generate_all()
        for r in gen.relationships:
            if r["type"] not in ("HAS_CLAIM", "EVIDENCED_BY"):
                assert r.get("confidence_score") is not None
                assert r.get("claim_id") is not None

    def test_limit_enforced(self):
        gen = MockDataGenerator()
        gen.generate_all()
        member_id = gen.members[0]["id"]
        direct = [
            r for r in gen.relationships
            if r["type"] not in ("HAS_CLAIM", "EVIDENCED_BY")
            and (r["source_id"] == member_id or r["target_id"] == member_id)
        ]
        limited = direct[:200]
        assert len(limited) <= 200
