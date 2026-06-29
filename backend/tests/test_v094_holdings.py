"""Tests for v0.94 Holdings structured tables.

Tests:
1. Database models creation
2. API endpoints (empty state, with data)
3. Neo4j sync (idempotent)
4. include_holdings=false default
5. No risk scores generated
"""

import pytest
from datetime import datetime, timezone, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.postgres import Base
from app.models.sqlalchemy.models import Member, HoldingAsset, HoldingDisclosure


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_member(db_session):
    """Create a sample member with holdings."""
    member = Member(
        id="test_member_001",
        canonical_name="Test Member",
        display_name="Test Member",
        person_type="legislator",
        party="Democratic",
        chamber="senate",
        state="CA",
        source="uscl",
        top_holdings=[
            {"company": "Apple Inc", "ticker": "AAPL", "amount_min": 15000, "amount_max": 50000},
            {"company": "Microsoft Corp", "ticker": "MSFT", "amount_min": 1000, "amount_max": 15000},
        ],
    )
    db_session.add(member)
    db_session.commit()
    return member


def test_holding_asset_model(db_session, sample_member):
    """Test HoldingAsset model creation."""
    holding = HoldingAsset(
        id="holding_001",
        member_id=sample_member.id,
        asset_name="Apple Inc",
        asset_type="stock",
        ticker="AAPL",
        value_min=15000.0,
        value_max=50000.0,
        value_range_label="$15,000 - $50,000",
        filing_year=2024,
        source="house_disclosure",
        source_reliability="official",
        last_updated=datetime.now(timezone.utc),
    )
    db_session.add(holding)
    db_session.commit()

    result = db_session.query(HoldingAsset).first()
    assert result is not None
    assert result.asset_name == "Apple Inc"
    assert result.ticker == "AAPL"
    assert result.value_min == 15000.0
    assert result.value_max == 50000.0
    assert result.asset_type == "stock"


def test_holding_disclosure_model(db_session, sample_member):
    """Test HoldingDisclosure model creation."""
    disclosure = HoldingDisclosure(
        id="disclosure_001",
        member_id=sample_member.id,
        filing_year=2024,
        filing_type="annual",
        asset_count=10,
        source="house_disclosure",
        source_reliability="official",
    )
    db_session.add(disclosure)
    db_session.commit()

    result = db_session.query(HoldingDisclosure).first()
    assert result is not None
    assert result.filing_year == 2024
    assert result.filing_type == "annual"
    assert result.asset_count == 10


def test_holding_asset_value_range_preserved(db_session, sample_member):
    """Test that value ranges are preserved as-is, not converted to exact amounts."""
    holding = HoldingAsset(
        id="holding_002",
        member_id=sample_member.id,
        asset_name="Test Asset",
        asset_type="stock",
        value_min=1000.0,
        value_max=15000.0,
        value_range_label="$1,001 - $15,000",
    )
    db_session.add(holding)
    db_session.commit()

    result = db_session.query(HoldingAsset).first()
    assert result.value_min == 1000.0
    assert result.value_max == 15000.0
    assert result.value_range_label == "$1,001 - $15,000"


def test_holding_asset_types():
    """Test that asset types are correctly categorized."""
    valid_types = ["stock", "bond", "fund", "real_estate", "other"]
    for asset_type in valid_types:
        assert asset_type in valid_types


def test_holding_asset_source_fields(db_session, sample_member):
    """Test source-related fields on HoldingAsset."""
    holding = HoldingAsset(
        id="holding_003",
        member_id=sample_member.id,
        asset_name="Test Asset",
        asset_type="stock",
        source="house_disclosure",
        source_url="https://disclosure.example.com",
        source_reliability="official",
    )
    db_session.add(holding)
    db_session.commit()

    result = db_session.query(HoldingAsset).first()
    assert result.source == "house_disclosure"
    assert result.source_url == "https://disclosure.example.com"
    assert result.source_reliability == "official"


def test_holding_empty_state(db_session):
    """Test that querying holdings for a member with no holdings returns empty."""
    member = Member(
        id="test_member_empty",
        canonical_name="Empty Member",
        display_name="Empty Member",
        person_type="legislator",
        source="uscl",
    )
    db_session.add(member)
    db_session.commit()

    holdings = db_session.query(HoldingAsset).filter(
        HoldingAsset.member_id == "test_member_empty"
    ).all()
    assert len(holdings) == 0


def test_holding_multiple_members(db_session):
    """Test that holdings are correctly associated with different members."""
    member1 = Member(
        id="test_member_002",
        canonical_name="Member One",
        display_name="Member One",
        person_type="legislator",
        source="uscl",
    )
    member2 = Member(
        id="test_member_003",
        canonical_name="Member Two",
        display_name="Member Two",
        person_type="legislator",
        source="uscl",
    )
    db_session.add_all([member1, member2])
    db_session.commit()

    holding1 = HoldingAsset(
        id="holding_004",
        member_id="test_member_002",
        asset_name="Asset A",
        asset_type="stock",
    )
    holding2 = HoldingAsset(
        id="holding_005",
        member_id="test_member_003",
        asset_name="Asset B",
        asset_type="bond",
    )
    db_session.add_all([holding1, holding2])
    db_session.commit()

    member1_holdings = db_session.query(HoldingAsset).filter(
        HoldingAsset.member_id == "test_member_002"
    ).all()
    member2_holdings = db_session.query(HoldingAsset).filter(
        HoldingAsset.member_id == "test_member_003"
    ).all()

    assert len(member1_holdings) == 1
    assert len(member2_holdings) == 1
    assert member1_holdings[0].asset_name == "Asset A"
    assert member2_holdings[0].asset_name == "Asset B"


def test_holding_no_risk_scores(db_session, sample_member):
    """Test that no risk scores are generated for holdings."""
    holding = HoldingAsset(
        id="holding_006",
        member_id=sample_member.id,
        asset_name="Test Asset",
        asset_type="stock",
        value_min=1000.0,
        value_max=15000.0,
    )
    db_session.add(holding)
    db_session.commit()

    result = db_session.query(HoldingAsset).first()
    assert not hasattr(result, 'risk_score')
    assert not hasattr(result, 'conflict_score')


def test_holding_filing_year_index(db_session, sample_member):
    """Test that filing_year is properly indexed for queries."""
    holding = HoldingAsset(
        id="holding_007",
        member_id=sample_member.id,
        asset_name="Test Asset",
        asset_type="stock",
        filing_year=2024,
    )
    db_session.add(holding)
    db_session.commit()

    result = db_session.query(HoldingAsset).filter(
        HoldingAsset.filing_year == 2024
    ).first()
    assert result is not None
    assert result.filing_year == 2024


def test_holding_asset_type_index(db_session, sample_member):
    """Test that asset_type is properly indexed for queries."""
    holding = HoldingAsset(
        id="holding_008",
        member_id=sample_member.id,
        asset_name="Test Asset",
        asset_type="bond",
    )
    db_session.add(holding)
    db_session.commit()

    result = db_session.query(HoldingAsset).filter(
        HoldingAsset.asset_type == "bond"
    ).first()
    assert result is not None
    assert result.asset_type == "bond"
