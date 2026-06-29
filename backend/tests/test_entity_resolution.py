"""Test entity resolution with mock aliases and dedup protection."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scripts.mock_data_generator import MockDataGenerator


class TestEntityResolution:
    def setup_method(self):
        self.gen = MockDataGenerator()
        self.gen.generate_all()

    def test_aliases_generated(self):
        members_with_aliases = [m for m in self.gen.members if m.get("aliases")]
        assert len(members_with_aliases) > 0, "No members have aliases"

    def test_org_aliases_generated(self):
        orgs_with_aliases = [o for o in self.gen.orgs if o.get("aliases")]
        assert len(orgs_with_aliases) > 0, "No orgs have aliases"

    def test_canonical_names_are_unique(self):
        names = [m["canonical_name"] for m in self.gen.members]
        assert len(names) == len(set(names)), "Duplicate member canonical names"

    def test_org_names_are_unique(self):
        names = [o["canonical_name"] for o in self.gen.orgs]
        assert len(names) == len(set(names)), "Duplicate org canonical names"

    def test_entity_ids_are_unique(self):
        all_ids = (
            [m["id"] for m in self.gen.members]
            + [o["id"] for o in self.gen.orgs]
            + [p["id"] for p in self.gen.pol_entities]
            + [e["id"] for e in self.gen.events]
        )
        assert len(all_ids) == len(set(all_ids)), "Duplicate entity IDs across types"
