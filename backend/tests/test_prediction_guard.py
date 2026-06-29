"""Tests for identity-only / committee-only prediction guard.

Verifies that when sandbox data only contains identity_claim and/or
committee_membership_claim (no term_claim), the prediction endpoint
returns predicted_position="unknown" with confidence_level="low".
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch
from app.api.routes.predictions import predict_vote
from app.models.pydantic.models import PredictionRequest, PredictionResponse
from app.models.sqlalchemy.models import Member
from app.models.sandbox_models import SandboxClaim


@pytest.fixture
def mock_member():
    m = MagicMock(spec=Member)
    m.id = "person_test_001"
    m.bioguide_id = "C000127"
    m.party = "Democrat"
    m.committee_memberships = ["SSAF"]
    m.top_contributors = []
    m.controversies = []
    return m


@pytest.fixture
def mock_event():
    e = MagicMock()
    e.id = "event_test_001"
    return e


def make_sandbox_claim(claim_type, subject_id="uscl_person_C000127"):
    c = MagicMock(spec=SandboxClaim)
    c.claim_id = f"uscl_claim_{claim_type}_test"
    c.claim_type = claim_type
    c.subject_id = subject_id
    return c


class TestIdentityOnlyGuard:
    def test_identity_only_returns_unknown(self, mock_member):
        """When only identity_claims exist, should return unknown."""
        identity_claim = make_sandbox_claim("identity_claim")

        mock_db = MagicMock()
        # Member query returns our mock member
        mock_db.query.return_value.filter.return_value.first.return_value = mock_member
        # SandboxClaim query returns only identity claims
        mock_db.query.return_value.filter.return_value.all.return_value = [identity_claim]

        request = PredictionRequest(member_id="person_test_001")

        result = predict_vote(request, db=mock_db)

        assert result.predicted_position == "unknown"
        assert result.confidence_level == "low"
        assert result.probability == 0.0
        assert "身份" in result.interpretation

    def test_identity_and_committee_only_returns_unknown(self, mock_member):
        """When only identity + committee claims exist (no term_claim), should return unknown."""
        identity_claim = make_sandbox_claim("identity_claim")
        committee_claim = make_sandbox_claim("committee_membership_claim")

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_member
        mock_db.query.return_value.filter.return_value.all.return_value = [
            identity_claim, committee_claim
        ]

        request = PredictionRequest(member_id="person_test_001")
        result = predict_vote(request, db=mock_db)

        assert result.predicted_position == "unknown"
        assert result.confidence_level == "low"

    def test_with_term_claims_proceeds_to_prediction(self, mock_member, mock_event):
        """When term_claims exist, should proceed to normal prediction."""
        identity_claim = make_sandbox_claim("identity_claim")
        term_claim = make_sandbox_claim("term_claim")

        mock_db = MagicMock()
        # Member query
        mock_db.query.return_value.filter.return_value.first.return_value = mock_member
        # SandboxClaim query returns identity + term claims (has term_claim)
        mock_db.query.return_value.filter.return_value.all.return_value = [
            identity_claim, term_claim
        ]

        request = PredictionRequest(member_id="person_test_001")
        result = predict_vote(request, db=mock_db)

        # Should not hit the identity-only guard
        assert result.predicted_position in ("support", "oppose", "uncertain")
        assert result.evidence_count >= 0  # proceeds to _compute_prediction

    def test_no_bioguide_skips_sandbox_check(self, mock_member, mock_event):
        """Members without bioguide_id should skip the sandbox check entirely."""
        mock_member.bioguide_id = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_member

        request = PredictionRequest(member_id="person_test_001")
        result = predict_vote(request, db=mock_db)

        # Should proceed to normal _compute_prediction
        assert result.predicted_position in ("support", "oppose", "uncertain")

    def test_no_sandbox_claims_proceeds_normally(self, mock_member, mock_event):
        """When sandbox has no claims for this member, proceed normally."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_member
        mock_db.query.return_value.filter.return_value.all.return_value = []

        request = PredictionRequest(member_id="person_test_001")
        result = predict_vote(request, db=mock_db)

        assert result.predicted_position in ("support", "oppose", "uncertain")

    def test_member_not_found_raises_error(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        request = PredictionRequest(member_id="nonexistent")
        with pytest.raises(Exception):
            predict_vote(request, db=mock_db)
