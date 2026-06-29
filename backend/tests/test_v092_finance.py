"""Tests for v0.92 campaign finance (FEC/OpenSecrets) integration."""

import pytest
from datetime import date
from app.models.sqlalchemy.models import CampaignCommittee, Donor, Contribution, Member
from app.models.pydantic.models import (
    ContributionsResponse, ContributionRecord, CommitteeBrief, DonorModel, ContributionSummary,
)


class TestCampaignFinanceModels:
    """CampaignFinance SQLAlchemy models exist with correct fields."""

    def test_campaign_committee_has_required_fields(self):
        assert hasattr(CampaignCommittee, "id")
        assert hasattr(CampaignCommittee, "fec_committee_id")
        assert hasattr(CampaignCommittee, "name")
        assert hasattr(CampaignCommittee, "candidate_id")
        assert hasattr(CampaignCommittee, "cycle")
        assert hasattr(CampaignCommittee, "source")

    def test_donor_has_required_fields(self):
        assert hasattr(Donor, "id")
        assert hasattr(Donor, "name")
        assert hasattr(Donor, "donor_type")
        assert hasattr(Donor, "industry")
        assert hasattr(Donor, "state")

    def test_contribution_has_required_fields(self):
        assert hasattr(Contribution, "id")
        assert hasattr(Contribution, "committee_id")
        assert hasattr(Contribution, "donor_id")
        assert hasattr(Contribution, "amount")
        assert hasattr(Contribution, "contribution_date")
        assert hasattr(Contribution, "cycle")
        assert hasattr(Contribution, "contribution_type")
        assert hasattr(Contribution, "source")


class TestContributionsResponse:
    """ContributionsResponse Pydantic model has correct structure."""

    def test_empty_response(self):
        resp = ContributionsResponse()
        assert resp.total_count == 0
        assert resp.committees == []
        assert resp.contributions == []
        assert resp.summary.total_received == 0.0

    def test_with_data(self):
        resp = ContributionsResponse(
            committees=[CommitteeBrief(id="c1", fec_committee_id="C001", name="Test Cmte")],
            contributions=[
                ContributionRecord(
                    id="x1",
                    committee=CommitteeBrief(id="c1", fec_committee_id="C001", name="Test Cmte"),
                    donor=DonorModel(id="d1", name="Big Donor"),
                    amount=50000.0,
                    cycle=2024,
                    contribution_type="individual",
                ),
            ],
            summary=ContributionSummary(
                total_received=50000.0,
                total_count=1,
                by_cycle={"2024": 50000.0},
                by_type={"individual": 50000.0},
                top_donors=[{"name": "Big Donor", "total": 50000.0, "count": 1, "type": "individual"}],
                top_industries=[{"industry": "未知", "total": 50000.0, "count": 1}],
            ),
            total_count=1,
        )
        assert resp.total_count == 1
        assert len(resp.committees) == 1
        assert resp.committees[0].name == "Test Cmte"
        assert resp.summary.total_received == 50000.0
        assert "2024" in resp.summary.by_cycle

    def test_top_donor_structure(self):
        """Top_donors list items have correct fields."""
        summary = ContributionSummary(
            top_donors=[
                {"name": "D1", "total": 100000.0, "count": 3, "type": "pac"},
                {"name": "D2", "total": 50000.0, "count": 1, "type": "individual"},
            ],
        )
        assert len(summary.top_donors) == 2
        assert summary.top_donors[0]["name"] == "D1"
        assert summary.top_donors[0]["total"] == 100000.0

    def test_top_industries_structure(self):
        summary = ContributionSummary(
            top_industries=[
                {"industry": "Defense", "total": 250000.0, "count": 5},
                {"industry": "Finance", "total": 150000.0, "count": 3},
            ],
        )
        assert len(summary.top_industries) == 2
        assert summary.top_industries[0]["industry"] == "Defense"


class TestFinanceGraphEdges:
    """Campaign finance edge types are defined in graph_service."""

    def test_finance_edge_types_defined(self):
        from app.services.graph_service import FINANCE_EDGE_TYPES
        assert "ASSOCIATED_WITH_COMMITTEE" in FINANCE_EDGE_TYPES
        assert "CONTRIBUTED_TO" in FINANCE_EDGE_TYPES
        assert "HAS_CONTRIBUTION_SOURCE" in FINANCE_EDGE_TYPES

    def test_finance_in_all_edges(self):
        from app.services.graph_service import EGO_EDGE_TYPES
        assert "ASSOCIATED_WITH_COMMITTEE" in EGO_EDGE_TYPES
        assert "CONTRIBUTED_TO" in EGO_EDGE_TYPES


class TestFinanceRouteImports:
    """Finance router module imports correctly."""

    def test_router_imports(self):
        from app.api.routes.finance import router
        routes = [r.path for r in router.routes]
        assert any("contributions" in r for r in routes)


class TestFECImportScript:
    """FEC import script functions exist."""

    def test_import_functions_exist(self):
        import app.etl.import_fec_data as mod
        assert hasattr(mod, "import_committees")
        assert hasattr(mod, "import_contributions")
        assert hasattr(mod, "download_and_extract_csv")
        assert hasattr(mod, "parse_amount")

    def test_parse_amount(self):
        from app.etl.import_fec_data import parse_amount
        assert parse_amount("5000") == 5000.0
        assert parse_amount("1,000.50") == 1000.5
        assert parse_amount("$2,500") == 2500.0
        assert parse_amount("invalid") == 0.0


class TestReportFinanceSection:
    """Report includes FEC contributions section."""

    def test_report_build_imports(self):
        from app.services.report_service import build_markdown
        assert callable(build_markdown)