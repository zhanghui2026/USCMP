"""SQLAlchemy ORM models for PostgreSQL."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, Date,
    DateTime, JSON, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from app.db.postgres import Base


class Member(Base):
    __tablename__ = "members"

    id = Column(String, primary_key=True)
    canonical_name = Column(String, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    aliases = Column(JSON, default=[])
    person_type = Column(String, nullable=False)
    party = Column(String, index=True)
    chamber = Column(String, index=True)
    state = Column(String(2), index=True)
    district = Column(String)
    official_photo_url = Column(String)
    bioguide_id = Column(String, unique=True, index=True)
    govtrack_id = Column(String)
    fec_candidate_id = Column(String)
    opensecrets_id = Column(String)
    top_contributors = Column(JSON, default=[])
    top_holdings = Column(JSON, default=[])
    committee_memberships = Column(JSON, default=[])
    career_summary = Column(JSON, default=[])
    china_stance_summary = Column(Text)
    core_positions = Column(Text)
    comprehensive_evaluation = Column(Text)
    controversies = Column(JSON, default=[])
    source = Column(String, nullable=False, default="mock", index=True)
    source_reliability = Column(String, default="mock")
    extraction_method = Column(String, default="mock")
    congress = Column(Integer, index=True)
    last_updated = Column(DateTime(timezone=True))
    latest_term_start = Column(String(16))
    latest_term_end = Column(String(16))
    is_current = Column(Boolean, default=False, index=True)
    member_scope = Column(String(16), default="current", index=True)
    official_ids = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    canonical_name = Column(String, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    aliases = Column(JSON, default=[])
    entity_type = Column(String, nullable=False, index=True)
    industry = Column(String, index=True)
    ticker = Column(String)
    country = Column(String, default="US")
    source_reliability = Column(String, default="mock")
    extraction_method = Column(String, default="mock")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id = Column(String, primary_key=True)
    source_name = Column(String, nullable=False, index=True)
    source_url = Column(String)
    title = Column(String)
    publisher = Column(String)
    published_at = Column(DateTime)
    collected_at = Column(DateTime)
    last_seen_at = Column(DateTime)
    document_type = Column(String, index=True)
    raw_text_hash = Column(String)
    snippet = Column(Text)
    source_reliability = Column(String, default="mock")
    license_note = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    event_date = Column(Date, nullable=False, index=True)
    congress = Column(Integer, index=True)
    source_reliability = Column(String, default="mock")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Claim(Base):
    __tablename__ = "claims"

    claim_id = Column(String, primary_key=True)
    claim_type = Column(String, nullable=False)
    subject_id = Column(String, nullable=False, index=True)
    object_id = Column(String, nullable=False, index=True)
    relation_type = Column(String, nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    original_snippet = Column(Text)
    confidence_score = Column(Float, nullable=False, default=0.5, index=True)
    extraction_method = Column(String, default="mock")
    source_reliability = Column(String, default="mock")
    review_status = Column(String, default="unreviewed")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class EtlSource(Base):
    __tablename__ = "etl_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String, nullable=False)
    source_url = Column(String)
    license_note = Column(String)
    robots_policy_note = Column(String)
    rate_limit = Column(String)
    supports_incremental = Column(Boolean, default=False)
    last_updated_at = Column(DateTime)
    data_freshness_window = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ApiRequestLog(Base):
    __tablename__ = "api_request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False)
    method = Column(String, nullable=False)
    status_code = Column(Integer)
    duration_ms = Column(Float)
    ip_address = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class MockSeedManifest(Base):
    __tablename__ = "mock_seed_manifest"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seed_version = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_count = Column(Integer, nullable=False)
    seed_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CampaignCommittee(Base):
    __tablename__ = "campaign_committees"

    id = Column(String, primary_key=True)
    fec_committee_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    party = Column(String)
    state = Column(String(2))
    chamber = Column(String)
    candidate_id = Column(String, ForeignKey("members.id"), index=True)
    cycle = Column(Integer)
    source = Column(String, default="fec")
    source_reliability = Column(String, default="official")
    fec_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    member = relationship("Member", backref="campaign_committees")


class Donor(Base):
    __tablename__ = "donors"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    donor_type = Column(String, default="individual", index=True)  # individual | pac | party | corporation
    industry = Column(String, index=True)
    employer = Column(String)
    city = Column(String)
    state = Column(String(2))
    source = Column(String, default="fec")
    source_reliability = Column(String, default="official")
    fec_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Contribution(Base):
    __tablename__ = "contributions"

    id = Column(String, primary_key=True)
    committee_id = Column(String, ForeignKey("campaign_committees.id"), nullable=False, index=True)
    donor_id = Column(String, ForeignKey("donors.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    contribution_date = Column(Date, index=True)
    cycle = Column(Integer, index=True)
    contribution_type = Column(String, index=True)  # individual | pac | party | transfer
    source = Column(String, default="fec")
    source_reliability = Column(String, default="official")
    fec_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    committee = relationship("CampaignCommittee", backref="contributions")
    donor = relationship("Donor", backref="contributions")


class MemberFinanceSummary(Base):
    __tablename__ = "member_finance_summary"

    member_id = Column(String, ForeignKey("members.id"), primary_key=True, index=True)
    total_received = Column(Float, default=0.0, nullable=False)
    total_count = Column(Integer, default=0, nullable=False)
    by_cycle = Column(JSON, default=dict)
    by_type = Column(JSON, default=dict)
    top_donors = Column(JSON, default=list)
    top_industries = Column(JSON, default=list)
    by_cycle_count = Column(JSON, default=dict)
    by_industry_count = Column(JSON, default=dict)
    data_mode = Column(String, default="full", index=True)
    source = Column(String, default="fec")
    source_reliability = Column(String, default="official")
    last_contribution_date = Column(Date)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    member = relationship("Member", backref="finance_summary")


class HoldingAsset(Base):
    __tablename__ = "holding_assets"

    id = Column(String, primary_key=True)
    member_id = Column(String, ForeignKey("members.id"), nullable=False, index=True)
    asset_name = Column(String, nullable=False, index=True)
    asset_type = Column(String, nullable=False, index=True)  # stock | bond | fund | real_estate | other
    ticker = Column(String, index=True)
    value_min = Column(Float)
    value_max = Column(Float)
    value_range_label = Column(String)  # e.g. "$1,001 - $15,000"
    filing_year = Column(Integer, index=True)
    disclosure_date = Column(Date)
    source = Column(String, default="house_disclosure")
    source_url = Column(String)
    source_reliability = Column(String, default="official")
    last_updated = Column(DateTime(timezone=True))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    member = relationship("Member", backref="holding_assets")


class HoldingDisclosure(Base):
    __tablename__ = "holding_disclosures"

    id = Column(String, primary_key=True)
    member_id = Column(String, ForeignKey("members.id"), nullable=False, index=True)
    filing_year = Column(Integer, nullable=False, index=True)
    filing_type = Column(String)  # annual | periodic | amendment
    filing_url = Column(String)
    filing_date = Column(Date)
    asset_count = Column(Integer, default=0)
    source = Column(String, default="house_disclosure")
    source_reliability = Column(String, default="official")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    member = relationship("Member", backref="holding_disclosures")


class MemberProfile(Base):
    __tablename__ = "member_profiles"

    id = Column(String, primary_key=True)
    member_id = Column(String, ForeignKey("members.id"), nullable=False, index=True)
    bioguide_id = Column(String, index=True)
    wikipedia_title = Column(String)
    wikipedia_url = Column(String)
    wikidata_qid = Column(String)
    image_url = Column(String)
    short_summary = Column(Text)
    birth_date = Column(String(32))
    birth_place = Column(String)
    education = Column(JSON, default=[])
    occupations = Column(JSON, default=[])
    career_highlights = Column(JSON, default=[])
    prior_positions = Column(JSON, default=[])
    military_service = Column(JSON, default=[])
    employers = Column(JSON, default=[])
    external_links = Column(JSON, default=[])
    profile_sources = Column(JSON, default=dict)
    profile_status = Column(String(32), default="summary_only")
    parsed_fields = Column(JSON, default=[])
    missing_fields = Column(JSON, default=[])
    source = Column(String, nullable=False, default="wikipedia")
    source_reliability = Column(String, default="external_open_content")
    last_updated = Column(DateTime(timezone=True))
    raw_snapshot_hash = Column(String(64))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    member = relationship("Member", backref="profile")
