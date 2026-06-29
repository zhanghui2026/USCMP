export interface MemberSummary {
  id: string;
  canonical_name: string;
  display_name: string;
  party?: string;
  chamber?: string;
  state?: string;
  district?: string;
  official_photo_url?: string;
  image_url?: string;
  committee_tags: string[];
  congress?: number;
  source: string;
  member_scope?: string;
}

export interface CommitteeMembership {
  committee: string;
  role: string;
  congress: number;
  committee_type: string;
  start_date?: string;
  end_date?: string;
}

export interface MemberDetail {
  id: string;
  canonical_name: string;
  display_name: string;
  aliases: string[];
  person_type: string;
  party?: string;
  chamber?: string;
  state?: string;
  district?: string;
  official_photo_url?: string;
  bioguide_id?: string;
  govtrack_id?: string;
  fec_candidate_id?: string;
  opensecrets_id?: string;
  top_contributors: Record<string, unknown>[];
  top_holdings: Record<string, unknown>[];
  committee_memberships: CommitteeMembership[];
  career_summary: Record<string, unknown>[];
  china_stance_summary?: string;
  core_positions?: string;
  comprehensive_evaluation?: string;
  controversies: Record<string, unknown>[];
  congress?: number;
  source: string;
  latest_term_start?: string;
  latest_term_end?: string;
  official_ids: Record<string, unknown>;
  last_updated?: string;
}

export interface OrganizationSummary {
  id: string;
  canonical_name: string;
  display_name: string;
  entity_type: string;
  industry?: string;
  ticker?: string;
  country?: string;
}

export interface EventModel {
  id: string;
  event_type: string;
  title: string;
  description?: string;
  event_date: string;
  congress?: number;
  source_reliability: string;
}

export interface GraphNode {
  id: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
  claim_id?: string;
  confidence_score?: number;
  start_date?: string;
  end_date?: string;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_node_count: number;
  truncated: boolean;
}

export interface ClaimModel {
  claim_id: string;
  claim_type: string;
  subject_id: string;
  object_id: string;
  relation_type: string;
  claim_text: string;
  original_snippet?: string;
  confidence_score: number;
  extraction_method: string;
  source_reliability: string;
  review_status: string;
}

export interface SourceDocumentModel {
  id: string;
  source_name: string;
  source_url?: string;
  title?: string;
  publisher?: string;
  published_at?: string;
  collected_at?: string;
  document_type?: string;
  snippet?: string;
  source_reliability: string;
  license_note?: string;
}

export interface EvidenceResponse {
  claim: ClaimModel;
  source_documents: SourceDocumentModel[];
}

export interface SearchResult {
  members: MemberSummary[];
  organizations: OrganizationSummary[];
  events: EventModel[];
  total_count: number;
}

export interface RadarMetric {
  metric_name: string;
  member_id: string;
  value: number;
}

export interface CompareResponse {
  members: MemberDetail[];
  radar_metrics: RadarMetric[];
  common_donors: Record<string, unknown>[];
  common_committees: Record<string, unknown>[];
  opposing_votes: Record<string, unknown>[];
  disclaimer: string;
}

export interface ReportResponse {
  format: string;
  content: string;
  generated_at: string;
  disclaimer: string;
}

export interface PredictionResponse {
  predicted_position: string;
  probability: number;
  confidence_interval: number[];
  top_factors: Record<string, unknown>[];
  counter_evidence: Record<string, unknown>[];
  evidence_count: number;
  data_quality_score: number;
  confidence_level: string;
  margin_from_baseline: number;
  interpretation: string;
  disclaimer: string;
}

export interface MemberListResponse {
  members: MemberSummary[];
  total: number;
  skip: number;
  limit: number;
}

export interface HealthResponse {
  status: string;
  postgres: string;
  neo4j: string;
  data_mode: string;
  version: string;
  timestamp: string;
}


export interface DataQualitySummaryResponse {
  total_nodes: number;
  total_edges: number;
  total_claims: number;
  total_source_documents: number;
  low_confidence_edges: number;
  needs_review_claims: number;
  source_reliability_distribution: Record<string, number>;
  extraction_method_distribution: Record<string, number>;
  node_type_distribution: Record<string, number>;
  edge_type_distribution: Record<string, number>;
  data_mode: string;
  sandbox_persons: number;
  sandbox_claims: number;
  sandbox_source_documents: number;
  sandbox_entity_resolution_safe: number;
  sandbox_entity_resolution_needs_review: number;
  generated_at: string;
}

export interface ApiError {
  error_code: string;
  message: string;
  details: Record<string, unknown>;
  request_id: string;
}

export interface CircleMember {
  member_id: string;
  display_name: string;
  party?: string;
  state?: string;
  shared_via: string;
}

export interface CircleCategory {
  circle_type: string;
  circle_name: string;
  evidence_type: string;
  source: string;
  source_url?: string;
  related_count: number;
  strength_level: string;
}

export interface CircleExpandResponse {
  circle_type: string;
  circle_name: string;
  members: CircleMember[];
}

export interface CircleResponse {
  categories: CircleCategory[];
}

export interface MemberProfileResponse {
  member_id: string;
  bioguide_id?: string;
  wikipedia_title?: string;
  wikipedia_url?: string;
  wikidata_qid?: string;
  image_url?: string;
  short_summary?: string;
  birth_date?: string;
  birth_place?: string;
  education: Record<string, unknown>[];
  occupations: string[];
  career_highlights: Record<string, unknown>[];
  prior_positions: Record<string, unknown>[];
  military_service: Record<string, unknown>[];
  employers: Record<string, unknown>[];
  profile_status: string;
  parsed_fields: string[];
  missing_fields: string[];
  source: string;
  source_reliability: string;
  last_updated?: string;
  profile_sources: Record<string, unknown>;
}

export interface CommitteeBrief {
  id: string;
  fec_committee_id: string;
  name: string;
  party?: string;
  state?: string;
  chamber?: string;
  cycle?: number;
}

export interface DonorModel {
  id: string;
  name: string;
  donor_type: string;
  industry?: string;
  employer?: string;
  city?: string;
  state?: string;
}

export interface ContributionRecord {
  id: string;
  committee: CommitteeBrief;
  donor: DonorModel;
  amount: number;
  contribution_date?: string;
  cycle?: number;
  contribution_type: string;
}

export interface ContributionSummary {
  total_received: number;
  total_count: number;
  by_cycle: Record<string, number>;
  by_type: Record<string, number>;
  top_donors: { name: string; total: number; count: number; type: string }[];
  top_industries: { industry: string; total: number; count: number }[];
}

export interface ContributionsResponse {
  committees: CommitteeBrief[];
  contributions: ContributionRecord[];
  summary: ContributionSummary;
  total_count: number;
  disclaimer: string;
}

export interface HoldingAssetRecord {
  id: string;
  asset_name: string;
  asset_type: string;
  ticker?: string;
  value_min?: number;
  value_max?: number;
  value_range_label?: string;
  filing_year?: number;
  disclosure_date?: string;
  source: string;
  source_url?: string;
  source_reliability: string;
}

export interface HoldingDisclosureRecord {
  id: string;
  filing_year: number;
  filing_type?: string;
  filing_url?: string;
  filing_date?: string;
  asset_count: number;
  source: string;
  source_reliability: string;
}

export interface HoldingsSummary {
  total_assets: number;
  by_asset_type: Record<string, number>;
  by_year: Record<string, number>;
  top_assets: Record<string, unknown>[];
}

export interface HoldingsResponse {
  holdings: HoldingAssetRecord[];
  disclosures: HoldingDisclosureRecord[];
  summary: HoldingsSummary;
  total_count: number;
  source: string;
  disclaimer: string;
}

export interface DataSourceCoverage {
  source_id: string;
  label: string;
  status: string;
  records: number;
  covered_members: number;
  note: string;
}

export interface DataCoverageResponse {
  sources: DataSourceCoverage[];
  generated_at: string;
}

export interface MemberFinanceSummaryResponse {
  member_id: string;
  total_received: number;
  total_count: number;
  by_cycle: Record<string, number>;
  by_type: Record<string, number>;
  top_donors: { id?: string; name: string; total: number; count: number; type?: string; industry?: string }[];
  top_industries: { industry: string; total?: number; count: number }[];
  by_cycle_count: Record<string, number>;
  by_industry_count: Record<string, number>;
  data_mode: string;
  source: string;
  source_reliability: string;
  last_contribution_date?: string;
  updated_at?: string;
}
