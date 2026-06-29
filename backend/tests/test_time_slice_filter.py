"""Test time slice filtering logic for graph queries."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from app.scripts.mock_data_generator import MockDataGenerator


class TestTimeSliceFilter:
    def setup_method(self):
        self.gen = MockDataGenerator()
        self.gen.generate_all()

    def test_edges_have_dates(self):
        main_rels = [
            r for r in self.gen.relationships
            if r["type"] not in ("HAS_CLAIM", "EVIDENCED_BY")
        ]
        for r in main_rels:
            assert r.get("start_date") is not None, f"Relation {r['id']} missing start_date"

    def test_filter_by_date_range(self):
        main_rels = [
            r for r in self.gen.relationships
            if r["type"] not in ("HAS_CLAIM", "EVIDENCED_BY")
            and r.get("start_date")
        ]
        cutoff = date(2020, 1, 1)
        filtered = [
            r for r in main_rels
            if date.fromisoformat(r["start_date"]) >= cutoff
        ]
        assert len(filtered) > 0, "No relations after 2020-01-01"
        assert len(filtered) < len(main_rels), "Filter should reduce results"

    def test_filter_by_congress(self):
        main_rels = [
            r for r in self.gen.relationships
            if r["type"] not in ("HAS_CLAIM", "EVIDENCED_BY")
            and r.get("congress")
        ]
        for congress in [117, 118, 119]:
            filtered = [r for r in main_rels if r["congress"] == congress]
            assert len(filtered) > 0, f"No relations for congress {congress}"

    def test_events_have_dates(self):
        for e in self.gen.events:
            assert e.get("event_date") is not None, f"Event {e['id']} missing event_date"

    def test_members_have_congress(self):
        for m in self.gen.members:
            assert m.get("congress") is not None, f"Member {m['id']} missing congress"
