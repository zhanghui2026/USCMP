import axios from 'axios';
import type {
  MemberListResponse, MemberDetail, GraphResponse,
  EvidenceResponse, SearchResult, CompareResponse,
  ReportResponse, PredictionResponse, HealthResponse,
  DataQualitySummaryResponse, MemberProfileResponse,
  DataCoverageResponse,
} from './types';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get('/health');
  return data;
}

export async function getMembers(params?: Record<string, unknown>): Promise<MemberListResponse> {
  const { data } = await api.get('/members', { params });
  return data;
}

export async function getMember(id: string): Promise<MemberDetail> {
  const { data } = await api.get(`/members/${id}`);
  return data;
}

export async function getMemberGraph(
  memberId: string, params?: Record<string, unknown>,
): Promise<GraphResponse> {
  const { data } = await api.get(`/members/${memberId}/graph`, { params });
  return data;
}

export async function expandGraph(body: Record<string, unknown>): Promise<GraphResponse> {
  const { data } = await api.post('/graph/expand', body);
  return data;
}

export async function getEvidence(claimId: string): Promise<EvidenceResponse> {
  const { data } = await api.get(`/evidence/${claimId}`);
  return data;
}

export async function search(params: Record<string, unknown>): Promise<SearchResult> {
  const { data } = await api.get('/search', { params });
  return data;
}

export async function compareMembers(body: Record<string, unknown>): Promise<CompareResponse> {
  const { data } = await api.post('/compare', body);
  return data;
}

export async function generateReport(body: Record<string, unknown>): Promise<ReportResponse> {
  const { data } = await api.post('/reports/markdown', body);
  return data;
}

export async function predictVote(body: Record<string, unknown>): Promise<PredictionResponse> {
  const { data } = await api.post('/predictions/vote', body);
  return data;
}

export async function getDataQuality(): Promise<DataQualitySummaryResponse> {
  const { data } = await api.get('/data-quality/summary');
  return data;
}

export async function getDataCoverage(): Promise<DataCoverageResponse> {
  const { data } = await api.get('/data-coverage');
  return data;
}

export async function getMemberProfile(memberId: string): Promise<MemberProfileResponse> {
  const { data } = await api.get(`/members/${memberId}/profile`);
  return data;
}

export async function getMemberCircles(memberId: string): Promise<import('./types').CircleResponse> {
  const { data } = await api.get(`/members/${memberId}/circles`);
  return data;
}

export async function getCircleMembers(memberId: string, circleType: string): Promise<import('./types').CircleExpandResponse> {
  const { data } = await api.get(`/members/${memberId}/circles/${circleType}`);
  return data;
}

export async function getMemberContributions(memberId: string, params?: { cycle?: number; limit?: number }): Promise<import('./types').ContributionsResponse> {
  const { data } = await api.get(`/members/${memberId}/contributions`, { params });
  return data;
}

export async function getMemberFinanceSummary(memberId: string): Promise<import('./types').MemberFinanceSummaryResponse> {
  const { data } = await api.get(`/members/${memberId}/finance/summary`);
  return data;
}

export async function getMemberHoldings(memberId: string, params?: { asset_type?: string; year?: number; limit?: number }): Promise<import('./types').HoldingsResponse> {
  const { data } = await api.get(`/members/${memberId}/holdings`, { params });
  return data;
}
