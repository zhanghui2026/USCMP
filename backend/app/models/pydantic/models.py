"""Pydantic v2 models for API request/response contracts."""

from datetime import date, datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class ApiError(BaseModel):
    error_code: str
    message: str
    details: dict = Field(default_factory=dict)
    request_id: str


class MemberSummary(BaseModel):
    id: str
    canonical_name: str
    display_name: str
    party: Optional[str] = None
    chamber: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    official_photo_url: Optional[str] = None
    image_url: Optional[str] = None
    committee_tags: list[str] = Field(default_factory=list)
    congress: Optional[int] = None
    source: str = "mock"
    member_scope: str = "current"


class CommitteeMembership(BaseModel):
    committee: str
    role: str
    congress: int
    committee_type: str = "committee"
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class MemberDetail(BaseModel):
    id: str
    canonical_name: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    person_type: str
    party: Optional[str] = None
    chamber: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    official_photo_url: Optional[str] = None
    bioguide_id: Optional[str] = None
    govtrack_id: Optional[str] = None
    fec_candidate_id: Optional[str] = None
    opensecrets_id: Optional[str] = None
    top_contributors: list[dict] = Field(default_factory=list)
    top_holdings: list[dict] = Field(default_factory=list)
    committee_memberships: list[CommitteeMembership] = Field(default_factory=list)
    career_summary: list[dict] = Field(default_factory=list)
    china_stance_summary: Optional[str] = None
    core_positions: Optional[str] = None
    comprehensive_evaluation: Optional[str] = None
    controversies: list[dict] = Field(default_factory=list)
    congress: Optional[int] = None
    source: str = "mock"
    latest_term_start: Optional[str] = None
    latest_term_end: Optional[str] = None
    official_ids: dict = Field(default_factory=dict)


class OrganizationSummary(BaseModel):
    id: str
    canonical_name: str
    display_name: str
    entity_type: str
    industry: Optional[str] = None
    ticker: Optional[str] = None
    country: Optional[str] = None


class PoliticalEntityModel(BaseModel):
    id: str
    name: str
    entity_type: str
    chamber: Optional[str] = None
    state: Optional[str] = None
    congress: Optional[int] = None


class EventModel(BaseModel):
    id: str
    event_type: str
    title: str
    description: Optional[str] = None
    event_date: date
    congress: Optional[int] = None
    source_reliability: str = "mock"


class GraphNode(BaseModel):
    id: str
    label: str
    properties: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: dict = Field(default_factory=dict)
    claim_id: Optional[str] = None
    confidence_score: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class GraphResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    total_node_count: int = 0
    truncated: bool = False


class GraphExpandRequest(BaseModel):
    node_id: str
    depth: int = Field(default=1, le=1)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=200, ge=1, le=500)
    include_finance: bool = False
    include_holdings: bool = False


class ClaimModel(BaseModel):
    claim_id: str
    claim_type: str
    subject_id: str
    object_id: str
    relation_type: str
    claim_text: str
    original_snippet: Optional[str] = None
    confidence_score: float
    extraction_method: str
    source_reliability: str
    review_status: str


class SourceDocumentModel(BaseModel):
    id: str
    source_name: str
    source_url: Optional[str] = None
    title: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    document_type: Optional[str] = None
    snippet: Optional[str] = None
    source_reliability: str
    license_note: Optional[str] = None


class EvidenceResponse(BaseModel):
    claim: ClaimModel
    source_documents: list[SourceDocumentModel] = Field(default_factory=list)


class SearchResult(BaseModel):
    members: list[MemberSummary] = Field(default_factory=list)
    organizations: list[OrganizationSummary] = Field(default_factory=list)
    events: list[EventModel] = Field(default_factory=list)
    total_count: int = 0
    source: str = "postgresql"


class RadarMetric(BaseModel):
    metric_name: str
    member_id: str
    value: float = Field(ge=0.0, le=100.0)
    source_reliability: str = "mock"


class CompareRequest(BaseModel):
    member_ids: list[str] = Field(min_length=2, max_length=10)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CompareResponse(BaseModel):
    members: list[MemberDetail] = Field(default_factory=list)
    radar_metrics: list[RadarMetric] = Field(default_factory=list)
    common_donors: list[dict] = Field(default_factory=list)
    common_committees: list[dict] = Field(default_factory=list)
    opposing_votes: list[dict] = Field(default_factory=list)
    disclaimer: str = "仅供研究参考，不构成事实认定、法律判断或投资建议。"


class ReportRequest(BaseModel):
    member_id: str
    format: str = "markdown"
    include_graph: bool = True
    include_predictions: bool = True


class ReportResponse(BaseModel):
    format: str
    content: str
    generated_at: datetime
    disclaimer: str


class PredictionRequest(BaseModel):
    member_id: str
    event_id: Optional[str] = None
    event_type: Optional[str] = None


class PredictionResponse(BaseModel):
    predicted_position: str
    probability: float = Field(ge=0.0, le=1.0)
    confidence_interval: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    top_factors: list[dict] = Field(default_factory=list)
    counter_evidence: list[dict] = Field(default_factory=list)
    evidence_count: int = 0
    data_quality_score: float = Field(ge=0.0, le=1.0)
    confidence_level: str = "unknown"
    margin_from_baseline: float = 0.0
    interpretation: str = ""
    disclaimer: str = "仅供研究参考，不构成事实认定、法律判断或投资建议。"


class MemberListResponse(BaseModel):
    members: list[MemberSummary] = Field(default_factory=list)
    total: int = 0
    skip: int = 0
    limit: int = 50


class HealthResponse(BaseModel):
    status: str
    postgres: str
    neo4j: str
    data_mode: str = "mock"
    version: str = "0.1.0"
    timestamp: datetime


class DataQualitySummaryResponse(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    total_claims: int = 0
    total_source_documents: int = 0
    low_confidence_edges: int = 0
    needs_review_claims: int = 0
    source_reliability_distribution: dict[str, int] = Field(default_factory=dict)
    extraction_method_distribution: dict[str, int] = Field(default_factory=dict)
    node_type_distribution: dict[str, int] = Field(default_factory=dict)
    edge_type_distribution: dict[str, int] = Field(default_factory=dict)
    data_mode: str = "mock"
    sandbox_persons: int = 0
    sandbox_claims: int = 0
    sandbox_source_documents: int = 0
    sandbox_entity_resolution_safe: int = 0
    sandbox_entity_resolution_needs_review: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ETLRunResponse(BaseModel):
    run_id: str
    status: str
    adapter: str
    commit_sha: str
    eligible_for_import: bool
    records_total: int
    started_at: str | None = None
    completed_at: str | None = None


class CircleMember(BaseModel):
    member_id: str
    display_name: str
    party: Optional[str] = None
    state: Optional[str] = None
    shared_via: str


class CircleCategory(BaseModel):
    circle_type: str
    circle_name: str
    evidence_type: str
    source: str
    source_url: Optional[str] = None
    related_count: int = 0
    strength_level: str  # weak | medium | strong


class CircleExpandResponse(BaseModel):
    circle_type: str
    circle_name: str
    members: list[CircleMember] = Field(default_factory=list)


class CircleResponse(BaseModel):
    categories: list[CircleCategory] = Field(default_factory=list)


class MemberProfileResponse(BaseModel):
    member_id: str
    bioguide_id: Optional[str] = None
    wikipedia_title: Optional[str] = None
    wikipedia_url: Optional[str] = None
    wikidata_qid: Optional[str] = None
    image_url: Optional[str] = None
    short_summary: Optional[str] = None
    birth_date: Optional[str] = None
    birth_place: Optional[str] = None
    education: list[dict] = Field(default_factory=list)
    occupations: list[str] = Field(default_factory=list)
    career_highlights: list[dict] = Field(default_factory=list)
    prior_positions: list[dict] = Field(default_factory=list)
    military_service: list[dict] = Field(default_factory=list)
    employers: list[dict] = Field(default_factory=list)
    profile_status: str = "summary_only"
    parsed_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    source: str = "wikipedia"
    source_reliability: str = "external_open_content"
    last_updated: Optional[str] = None
    profile_sources: dict = Field(default_factory=dict)


class ETLSandboxStatsResponse(BaseModel):
    total_persons: int = 0
    total_committees: int = 0
    total_claims: int = 0
    import_runs: int = 0
    entity_resolution: dict[str, int] = Field(default_factory=dict)
    claim_types: dict[str, int] = Field(default_factory=dict)
    data_namespace: str = "sandbox"
    data_source: str = "unitedstates/congress-legislators"


class CommitteeBrief(BaseModel):
    id: str
    fec_committee_id: str
    name: str
    party: Optional[str] = None
    state: Optional[str] = None
    chamber: Optional[str] = None
    cycle: Optional[int] = None


class DonorModel(BaseModel):
    id: str
    name: str
    donor_type: str = "individual"
    industry: Optional[str] = None
    employer: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None


class ContributionRecord(BaseModel):
    id: str
    committee: CommitteeBrief
    donor: DonorModel
    amount: float
    contribution_date: Optional[date] = None
    cycle: Optional[int] = None
    contribution_type: str = "individual"


class ContributionSummary(BaseModel):
    total_received: float = 0.0
    total_count: int = 0
    by_cycle: dict[str, float] = Field(default_factory=dict)
    by_type: dict[str, float] = Field(default_factory=dict)
    top_donors: list[dict] = Field(default_factory=list)
    top_industries: list[dict] = Field(default_factory=list)


class ContributionsResponse(BaseModel):
    committees: list[CommitteeBrief] = Field(default_factory=list)
    contributions: list[ContributionRecord] = Field(default_factory=list)
    summary: ContributionSummary = Field(default_factory=ContributionSummary)
    total_count: int = 0
    disclaimer: str = "数据来源: FEC.gov ( bulk-downloads ) 及 OpenSecrets.org。仅供研究参考。"


class MemberFinanceSummaryResponse(BaseModel):
    member_id: str
    total_received: float = 0.0
    total_count: int = 0
    by_cycle: dict[str, float] = Field(default_factory=dict)
    by_type: dict[str, float] = Field(default_factory=dict)
    top_donors: list[dict] = Field(default_factory=list)
    top_industries: list[dict] = Field(default_factory=list)
    by_cycle_count: dict[str, int] = Field(default_factory=dict)
    by_industry_count: dict[str, int] = Field(default_factory=dict)
    data_mode: str = "full"
    source: str = "fec"
    source_reliability: str = "official"
    last_contribution_date: Optional[date] = None
    updated_at: Optional[datetime] = None


class HoldingAssetRecord(BaseModel):
    id: str
    asset_name: str
    asset_type: str = "stock"
    ticker: Optional[str] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_range_label: Optional[str] = None
    filing_year: Optional[int] = None
    disclosure_date: Optional[date] = None
    source: str = "house_disclosure"
    source_url: Optional[str] = None
    source_reliability: str = "official"


class HoldingDisclosureRecord(BaseModel):
    id: str
    filing_year: int
    filing_type: Optional[str] = None
    filing_url: Optional[str] = None
    filing_date: Optional[date] = None
    asset_count: int = 0
    source: str = "house_disclosure"
    source_reliability: str = "official"


class HoldingsSummary(BaseModel):
    total_assets: int = 0
    by_asset_type: dict[str, int] = Field(default_factory=dict)
    by_year: dict[str, int] = Field(default_factory=dict)
    top_assets: list[dict] = Field(default_factory=list)


class HoldingsResponse(BaseModel):
    holdings: list[HoldingAssetRecord] = Field(default_factory=list)
    disclosures: list[HoldingDisclosureRecord] = Field(default_factory=list)
    summary: HoldingsSummary = Field(default_factory=HoldingsSummary)
    total_count: int = 0
    source: str = "house_disclosure"
    disclaimer: str = "持股披露数据来源于国会财务公开报告。金额为区间值，不构成精确估值。不构成投资建议、法律判断或利益冲突判断。"


class DataSourceCoverage(BaseModel):
    source_id: str
    label: str
    status: str
    records: int = 0
    covered_members: int = 0
    note: str = ""


class DataCoverageResponse(BaseModel):
    sources: list[DataSourceCoverage] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
