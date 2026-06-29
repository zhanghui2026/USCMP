"""Test graph_service date filtering is correctly wired into Cypher queries."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from unittest.mock import patch
from app.services.graph_service import get_member_graph, expand_node


def _call_args(fn, call_index=0):
    """Extract (cypher, params) from the nth mock call."""
    return fn.call_args_list[call_index][0]


class TestGraphServiceDateFilter:
    def test_no_date_filter_passes_none_params(self):
        """When no dates provided, start_date and end_date params are None."""
        with patch("app.services.graph_service.run_cypher", return_value=[]) as mock_run:
            get_member_graph("person_test", depth=1)

        cypher, params = _call_args(mock_run)
        assert params["start_date"] is None
        assert params["end_date"] is None

    def test_get_member_graph_depth1_with_start_date(self):
        """start_date is passed as a string param and used in Cypher."""
        with patch("app.services.graph_service.run_cypher", return_value=[]) as mock_run:
            get_member_graph("person_test", depth=1, start_date=date(2023, 1, 1))

        cypher, params = _call_args(mock_run)
        assert params["start_date"] == "2023-01-01"
        assert params["end_date"] is None
        assert "coalesce(r.start_date" in cypher
        assert "$start_date" in cypher

    def test_get_member_graph_depth1_with_end_date(self):
        """end_date is passed as a string param and used in Cypher."""
        with patch("app.services.graph_service.run_cypher", return_value=[]) as mock_run:
            get_member_graph("person_test", depth=1, end_date=date(2025, 6, 1))

        cypher, params = _call_args(mock_run)
        assert params["start_date"] is None
        assert params["end_date"] == "2025-06-01"
        assert "coalesce(r.end_date" in cypher
        assert "$end_date" in cypher

    def test_get_member_graph_depth1_with_both_dates(self):
        """Both start_date and end_date are passed and appear in Cypher."""
        with patch("app.services.graph_service.run_cypher", return_value=[]) as mock_run:
            get_member_graph("person_test", depth=1,
                             start_date=date(2023, 1, 1),
                             end_date=date(2025, 6, 1))

        cypher, params = _call_args(mock_run)
        assert params["start_date"] == "2023-01-01"
        assert params["end_date"] == "2025-06-01"
        assert "$start_date" in cypher
        assert "$end_date" in cypher

    def test_get_member_graph_depth2_receives_date_filter_on_both_hops(self):
        """Depth=2 query includes date filter on both r1 and r2 when include_related_people=True."""
        with patch("app.services.graph_service.run_cypher", return_value=[]) as mock_run:
            get_member_graph("person_test", depth=2, start_date=date(2023, 1, 1),
                             include_related_people=True)

        cypher, params = _call_args(mock_run)
        assert params["start_date"] == "2023-01-01"
        assert "coalesce(r1.start_date" in cypher
        assert "coalesce(r2.start_date" in cypher

    def test_expand_node_with_date_filter(self):
        """expand_node passes date params and includes them in Cypher."""
        with patch("app.services.graph_service.run_cypher", return_value=[]) as mock_run:
            expand_node("org_test",
                        start_date=date(2023, 1, 1),
                        end_date=date(2025, 6, 1))

        cypher, params = _call_args(mock_run)
        assert params["start_date"] == "2023-01-01"
        assert params["end_date"] == "2025-06-01"
        assert "coalesce(r.start_date" in cypher
        assert "coalesce(r.end_date" in cypher

    def test_expand_node_without_dates(self):
        """expand_node without dates passes None params."""
        with patch("app.services.graph_service.run_cypher", return_value=[]) as mock_run:
            expand_node("org_test")

        cypher, params = _call_args(mock_run)
        assert params["start_date"] is None
        assert params["end_date"] is None
        assert "coalesce(r.start_date" in cypher
        assert "$start_date" in cypher

    def test_service_returns_truncated_flag(self):
        """Return dict still includes truncated flag correctly."""
        fake_records = list(range(5))
        with patch("app.services.graph_service.run_cypher", return_value=fake_records):
            result = get_member_graph("person_test", depth=1, limit=3)

        assert result["records"] == fake_records
        assert result["truncated"] is True
