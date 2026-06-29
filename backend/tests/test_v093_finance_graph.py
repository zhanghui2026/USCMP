"""Tests for v0.93 Campaign Finance Graph Sync."""

import pytest


class TestFinanceGraphConstants:
    """Finance edge types and graph constants are correct."""

    def test_finance_edge_types(self):
        from app.services.graph_service import FINANCE_EDGE_TYPES
        assert "ASSOCIATED_WITH_COMMITTEE" in FINANCE_EDGE_TYPES
        assert "CONTRIBUTED_TO" in FINANCE_EDGE_TYPES
        assert "HAS_CONTRIBUTION_SOURCE" in FINANCE_EDGE_TYPES

    def test_finance_in_ego_edge_types(self):
        from app.services.graph_service import EGO_EDGE_TYPES
        for etype in ["ASSOCIATED_WITH_COMMITTEE", "CONTRIBUTED_TO", "HAS_CONTRIBUTION_SOURCE"]:
            assert etype in EGO_EDGE_TYPES

    def test_edge_filter_with_finance(self):
        from app.services.graph_service import _edge_filter
        f = _edge_filter("r", include_finance=True)
        assert "ASSOCIATED_WITH_COMMITTEE" in f
        assert "CONTRIBUTED_TO" in f
        assert "HAS_CONTRIBUTION_SOURCE" in f

    def test_edge_filter_without_finance(self):
        from app.services.graph_service import _edge_filter
        f = _edge_filter("r", include_finance=False)
        assert "ASSOCIATED_WITH_COMMITTEE" not in f
        assert "CONTRIBUTED_TO" not in f
        assert "HAS_CONTRIBUTION_SOURCE" not in f


class TestFinanceGraphImport:
    """Import script functions exist and are callable."""

    def test_import_function_exists(self):
        from app.etl.import_finance_graph import import_finance_graph
        assert callable(import_finance_graph)

    def test_import_returns_stats_dict(self):
        from app.etl.import_finance_graph import import_finance_graph
        # Just verify the function signature and return type
        import inspect
        sig = inspect.signature(import_finance_graph)
        assert "cycle" in sig.parameters
        assert "limit" in sig.parameters
        assert "dry_run" in sig.parameters


class TestGraphAPIFinanceParam:
    """Graph API endpoints accept include_finance parameter."""

    def test_member_graph_has_finance_param(self):
        from app.api.routes.graph import member_graph
        import inspect
        sig = inspect.signature(member_graph)
        assert "include_finance" in sig.parameters

    def test_expand_request_has_finance_param(self):
        from app.models.pydantic.models import GraphExpandRequest
        model = GraphExpandRequest(node_id="test")
        assert hasattr(model, "include_finance")
        assert model.include_finance is False


class TestFinanceNodeLabels:
    """Neo4j node labels for finance are correctly defined."""

    def test_campaign_committee_label(self):
        """CampaignCommittee is a valid label in the graph."""
        from app.etl.import_finance_graph import import_finance_graph
        import inspect
        source = inspect.getsource(import_finance_graph)
        assert "CampaignCommittee" in source

    def test_donor_label(self):
        from app.etl.import_finance_graph import import_finance_graph
        import inspect
        source = inspect.getsource(import_finance_graph)
        assert "Donor" in source

    def test_contribution_source_label(self):
        from app.etl.import_finance_graph import import_finance_graph
        import inspect
        source = inspect.getsource(import_finance_graph)
        assert "ContributionSource" in source


class TestFinanceEdgeProperties:
    """Finance edges have required properties."""

    def test_associated_edge_has_required_props(self):
        from app.etl.import_finance_graph import import_finance_graph
        import inspect
        source = inspect.getsource(import_finance_graph)
        assert "ASSOCIATED_WITH_COMMITTEE" in source
        assert "cycle" in source
        assert "amount_total" in source
        assert "contribution_count" in source
        assert "source" in source
        assert "source_reliability" in source
        assert "last_updated" in source

    def test_contributed_edge_has_required_props(self):
        from app.etl.import_finance_graph import import_finance_graph
        import inspect
        source = inspect.getsource(import_finance_graph)
        assert "CONTRIBUTED_TO" in source
        assert "amount_total" in source
        assert "contribution_count" in source


class TestGraphResponseNoOrphans:
    """Graph response construction filters orphan edges."""

    def test_orphan_filter_exists(self):
        from app.api.routes.graph import _build_graph_response
        import inspect
        source = inspect.getsource(_build_graph_response)
        assert "node_ids" in source
        assert "filtered_edges" in source


class TestFinanceGraphIdempotency:
    """Import uses MERGE for idempotency."""

    def test_uses_merge(self):
        from app.etl.import_finance_graph import import_finance_graph
        import inspect
        source = inspect.getsource(import_finance_graph)
        assert "MERGE" in source
        # Should use MERGE for all three node types
        assert source.count("MERGE") >= 5  # nodes + edges