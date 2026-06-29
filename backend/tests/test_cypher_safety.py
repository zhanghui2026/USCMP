"""Test Cypher query safety: no unbounded patterns, LIMIT present, no injection vectors."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCypherSafety:
    def test_no_unbounded_pattern_in_mock_gen(self):
        """Verify mock generator does not use unbounded graph patterns."""
        import inspect
        from app.scripts import mock_data_generator
        source = inspect.getsource(mock_data_generator)
        # Check no unbounded patterns: MATCH (a)-[*]->(b) without depth limit
        assert "-[*]->" not in source, "Unbounded graph pattern found in code"

    def test_seed_script_has_limit_logic(self):
        import inspect
        from app.scripts import seed_mock_data
        source = inspect.getsource(seed_mock_data)
        assert "LIMIT" in source.upper() or "limit" in source.lower(), (
            "No LIMIT enforcement found in seed script"
        )

    def test_graph_service_not_splicing_inputs(self):
        """Ensure graph_service.py uses parameterized queries, not string concatenation."""
        import inspect
        from app.services import graph_service
        source = inspect.getsource(graph_service)
        # Should use query parameters, not f-string in cypher
        forbidden = ["f\"MATCH", "f'MATCH", "\"MATCH (\" +"]
        for pattern in forbidden:
            assert pattern not in source, f"Potential injection vector: {pattern}"
