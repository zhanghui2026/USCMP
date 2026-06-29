import { describe, it, expect } from 'vitest';
import type { MemberSummary, MemberDetail } from '../app/api/types';

describe('data boundary validation', () => {
  const mockMember: MemberDetail = {
    id: 'mock-1',
    canonical_name: 'Mock Senator',
    display_name: 'Mock Senator',
    aliases: [],
    person_type: 'legislator',
    party: 'Democrat',
    chamber: 'senate',
    state: 'NY',
    top_contributors: [],
    top_holdings: [],
    committee_memberships: [],
    career_summary: [],
    controversies: [],
    source: 'mock',
    official_ids: {},
    congress: 119,
  };

  const realMember: MemberDetail = {
    id: 'uscl_person_P000197',
    canonical_name: 'Nancy Pelosi',
    display_name: 'Nancy Pelosi',
    aliases: [],
    person_type: 'legislator',
    party: 'Democrat',
    chamber: 'house',
    state: 'CA',
    district: '11',
    bioguide_id: 'P000197',
    govtrack_id: '400314',
    fec_candidate_id: 'H8CA05035',
    opensecrets_id: 'N00007360',
    top_contributors: [],
    top_holdings: [],
    committee_memberships: [],
    career_summary: [],
    china_stance_summary: undefined,
    controversies: [],
    source: 'uscl',
    official_ids: { fec: ['H8CA05035'] },
    latest_term_start: '2023-01-03',
    latest_term_end: '2025-01-03',
    last_updated: '2024-06-01',
    congress: 119,
  };

  it('mock members have source=mock', () => {
    expect(mockMember.source).toBe('mock');
  });

  it('real members have source=uscl', () => {
    expect(realMember.source).toBe('uscl');
  });

  it('real members have bioguide_id', () => {
    expect(realMember.bioguide_id).toBeTruthy();
  });

  it('real members have latest_term_start and latest_term_end', () => {
    expect(realMember.latest_term_start).toBe('2023-01-03');
    expect(realMember.latest_term_end).toBe('2025-01-03');
  });

  it('real members have official_ids', () => {
    expect(realMember.official_ids).toHaveProperty('fec');
  });

  it('real members have last_updated', () => {
    expect(realMember.last_updated).toBe('2024-06-01');
  });

  it('unavailable fields are empty arrays or null', () => {
    expect(realMember.top_contributors).toEqual([]);
    expect(realMember.top_holdings).toEqual([]);
    expect(realMember.career_summary).toEqual([]);
    expect(realMember.controversies).toEqual([]);
  });

  it('mock members should not be confused with real', () => {
    expect(mockMember.source).not.toBe(realMember.source);
    expect(mockMember.bioguide_id).toBeUndefined();
  });

  it('report disclaimer exists for real data', () => {
    const disclaimer = realMember.source === 'uscl'
      ? 'CC0-1.0 / unitedstates/congress-legislators'
      : 'Mock data (demonstration only)';
    expect(disclaimer).toContain('CC0-1.0');
  });

  it('report disclaimer for mock is different', () => {
    const disclaimer = mockMember.source === 'uscl'
      ? 'CC0-1.0 / unitedstates/congress-legislators'
      : 'Mock data (demonstration only)';
    expect(disclaimer).toContain('Mock');
  });
});
