"""Sandbox SQLAlchemy models for real data import.

All sandbox tables use namespace isolation:
- data_namespace = "sandbox"
- data_source = "unitedstates/congress-legislators"
- source_reliability = "secondary"

These tables never merge into mock tables without explicit approval.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey,
)
from sqlalchemy.orm import declarative_base

SandboxBase = declarative_base()


def _now():
    return datetime.now(timezone.utc)


class SandboxImportRun(SandboxBase):
    __tablename__ = "sandbox_import_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="dry_run_completed")
    adapter = Column(String(128), nullable=False)
    commit_sha = Column(String(64), nullable=False)
    source_name = Column(String(256), nullable=False)
    source_reliability = Column(String(32), nullable=False, default="secondary")
    license_note = Column(String(64), nullable=False, default="CC0-1.0")
    dry_run_only = Column(Boolean, default=True)
    eligible_for_import = Column(Boolean, default=False)
    started_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    completed_at = Column(DateTime(timezone=True))
    files_processed = Column(Integer, default=0)
    records_total = Column(Integer, default=0)
    data_namespace = Column(String(32), nullable=False, default="sandbox")
    data_source = Column(String(256), nullable=False, default="unitedstates/congress-legislators")
    etl_run_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class SandboxPerson(SandboxBase):
    __tablename__ = "sandbox_persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(String(64), unique=True, nullable=False, index=True)
    canonical_name = Column(String(256), nullable=False)
    display_name = Column(String(256))
    aliases = Column(JSON, default=[])
    person_type = Column(String(64), nullable=False, default="legislator")
    party = Column(String(64))
    chamber = Column(String(16))
    state = Column(String(8))
    district = Column(String(8))
    bioguide_id = Column(String(16), index=True)
    govtrack_id = Column(String(16), index=True)
    opensecrets_id = Column(String(16))
    fec_ids = Column(JSON, default=[])
    latest_term_start = Column(String(16))
    latest_term_end = Column(String(16))
    data_namespace = Column(String(32), nullable=False, default="sandbox")
    data_source = Column(String(256), nullable=False, default="unitedstates/congress-legislators")
    source_reliability = Column(String(32), nullable=False, default="secondary")
    etl_run_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class SandboxPersonTerm(SandboxBase):
    __tablename__ = "sandbox_person_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    term_id = Column(String(64), unique=True, nullable=False, index=True)
    person_id = Column(String(64), nullable=False, index=True)
    congress = Column(Integer)
    chamber = Column(String(16))
    state = Column(String(8))
    district = Column(String(8))
    party = Column(String(64))
    term_type = Column(String(16))
    start_date = Column(String(16))
    end_date = Column(String(16))
    claim_id = Column(String(64))
    confidence_score = Column(Float, default=0.90)
    data_namespace = Column(String(32), nullable=False, default="sandbox")
    data_source = Column(String(256), nullable=False, default="unitedstates/congress-legislators")
    source_reliability = Column(String(32), nullable=False, default="secondary")
    etl_run_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class SandboxPoliticalEntity(SandboxBase):
    __tablename__ = "sandbox_political_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(256), nullable=False)
    entity_type = Column(String(32), nullable=False, default="committee")
    chamber = Column(String(16))
    thomas_id = Column(String(16), index=True)
    url = Column(String(512))
    congress = Column(Integer)
    data_namespace = Column(String(32), nullable=False, default="sandbox")
    data_source = Column(String(256), nullable=False, default="unitedstates/congress-legislators")
    source_reliability = Column(String(32), nullable=False, default="secondary")
    etl_run_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class SandboxCommitteeMembership(SandboxBase):
    __tablename__ = "sandbox_committee_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    membership_id = Column(String(64), unique=True, nullable=False, index=True)
    person_id = Column(String(64), nullable=False, index=True)
    committee_entity_id = Column(String(64), nullable=False, index=True)
    role = Column(String(64))
    rank = Column(String(32))
    party = Column(String(64))
    congress = Column(Integer)
    start_date = Column(String(16))
    end_date = Column(String(16))
    claim_id = Column(String(64))
    confidence_score = Column(Float, default=0.85)
    review_status = Column(String(32), default="needs_review")
    data_namespace = Column(String(32), nullable=False, default="sandbox")
    data_source = Column(String(256), nullable=False, default="unitedstates/congress-legislators")
    source_reliability = Column(String(32), nullable=False, default="secondary")
    etl_run_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class SandboxSocialAccount(SandboxBase):
    __tablename__ = "sandbox_social_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(64), unique=True, nullable=False, index=True)
    person_id = Column(String(64), nullable=False, index=True)
    platform = Column(String(32), nullable=False)
    account = Column(String(256), nullable=False)
    official = Column(Boolean, default=True)
    claim_id = Column(String(64))
    confidence_score = Column(Float, default=0.85)
    data_namespace = Column(String(32), nullable=False, default="sandbox")
    data_source = Column(String(256), nullable=False, default="unitedstates/congress-legislators")
    source_reliability = Column(String(32), nullable=False, default="secondary")
    etl_run_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class SandboxClaim(SandboxBase):
    __tablename__ = "sandbox_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(String(64), unique=True, nullable=False, index=True)
    claim_type = Column(String(64), nullable=False)
    subject_id = Column(String(64), nullable=False)
    object_id = Column(String(64), nullable=False)
    relation_type = Column(String(64))
    claim_text = Column(Text)
    confidence_score = Column(Float, default=0.85)
    extraction_method = Column(String(32), nullable=False, default="yaml")
    source_reliability = Column(String(32), nullable=False, default="secondary")
    review_status = Column(String(32), default="needs_review")
    data_namespace = Column(String(32), nullable=False, default="sandbox")
    data_source = Column(String(256), nullable=False, default="unitedstates/congress-legislators")
    etl_run_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class SandboxSourceDocument(SandboxBase):
    __tablename__ = "sandbox_source_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(64), unique=True, nullable=False, index=True)
    source_name = Column(String(256), nullable=False)
    source_url = Column(String(512))
    title = Column(String(256))
    publisher = Column(String(256))
    document_type = Column(String(64), nullable=False, default="structured_dataset")
    source_reliability = Column(String(32), nullable=False, default="secondary")
    license_note = Column(String(64), default="CC0-1.0")
    sha256 = Column(String(64))
    record_count = Column(Integer, default=0)
    data_namespace = Column(String(32), nullable=False, default="sandbox")
    data_source = Column(String(256), nullable=False, default="unitedstates/congress-legislators")
    etl_run_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class SandboxEntityResolutionReview(SandboxBase):
    __tablename__ = "sandbox_entity_resolution_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String(64), unique=True, nullable=False, index=True)
    sandbox_person_id = Column(String(64), nullable=False, index=True)
    mock_person_id = Column(String(64), index=True)
    match_type = Column(String(32), nullable=False)
    match_score = Column(Float)
    needs_review = Column(Boolean, default=True)
    safe_match = Column(Boolean, default=False)
    resolution_status = Column(String(32), default="pending")
    notes = Column(Text)
    data_namespace = Column(String(32), nullable=False, default="sandbox")
    etl_run_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
