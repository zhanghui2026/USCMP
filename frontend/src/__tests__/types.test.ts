import { describe, it, expect } from 'vitest';
import type {
  MemberSummary,
  MemberDetail,
  HealthResponse,
  GraphResponse,
  SearchResult,
  ReportResponse,
  MemberProfileResponse,
} from '../app/api/types';

describe('type definitions', () => {
  describe('MemberSummary', () => {
    it('requires id, canonical_name, display_name, source', () => {
      const m: MemberSummary = {
        id: 'test-1',
        canonical_name: 'Test User',
        display_name: 'Test',
        committee_tags: [],
        source: 'mock',
      };
      expect(m.id).toBe('test-1');
      expect(m.source).toBe('mock');
    });

    it('supports uscl source', () => {
      const m: MemberSummary = {
        id: 'test-2',
        canonical_name: 'Real User',
        display_name: 'Real',
        committee_tags: [],
        source: 'uscl',
        party: 'Democrat',
        chamber: 'house',
        state: 'CA',
        congress: 119,
      };
      expect(m.source).toBe('uscl');
      expect(m.congress).toBe(119);
    });
  });

  describe('MemberDetail', () => {
    it('includes new v0.5 fields', () => {
      const m: MemberDetail = {
        id: 'test-1',
        canonical_name: 'Test',
        display_name: 'Test',
        aliases: [],
        person_type: 'legislator',
        top_contributors: [],
        top_holdings: [],
        committee_memberships: [],
        career_summary: [],
        controversies: [],
        source: 'uscl',
        official_ids: { fec: ['H0CA00001'] },
        latest_term_start: '2023-01-03',
        latest_term_end: '2025-01-03',
        last_updated: '2024-06-01',
        congress: 118,
      };
      expect(m.source).toBe('uscl');
      expect(m.official_ids).toEqual({ fec: ['H0CA00001'] });
      expect(m.latest_term_start).toBe('2023-01-03');
      expect(m.latest_term_end).toBe('2025-01-03');
      expect(m.last_updated).toBe('2024-06-01');
    });

    it('allows null for optional new fields', () => {
      const m: MemberDetail = {
        id: 'test-2',
        canonical_name: 'Mock',
        display_name: 'Mock',
        aliases: [],
        person_type: 'legislator',
        top_contributors: [],
        top_holdings: [],
        committee_memberships: [],
        career_summary: [],
        controversies: [],
        source: 'mock',
        official_ids: {},
        latest_term_start: undefined,
        latest_term_end: undefined,
        last_updated: undefined,
      };
      expect(m.source).toBe('mock');
      expect(m.official_ids).toEqual({});
      expect(m.latest_term_start).toBeUndefined();
      expect(m.last_updated).toBeUndefined();
    });
  });

  describe('HealthResponse', () => {
    it('has data_mode field', () => {
      const h: HealthResponse = {
        status: 'ok',
        postgres: 'ok',
        neo4j: 'ok',
        data_mode: 'mixed',
        version: '0.1.0',
        timestamp: '2024-01-01T00:00:00Z',
      };
      expect(h.data_mode).toBe('mixed');
    });
  });

  describe('GraphResponse', () => {
    it('accepts real relationship types', () => {
      const g: GraphResponse = {
        nodes: [
          { id: 'p1', label: 'Person', properties: {} },
          { id: 'party_democrat', label: 'Party', properties: { name: 'Democrat' } },
        ],
        edges: [
          {
            id: 'e1',
            source: 'p1',
            target: 'party_democrat',
            type: 'MEMBER_OF_PARTY',
            properties: {},
          },
        ],
        total_node_count: 2,
        truncated: false,
      };
      expect(g.edges[0].type).toBe('MEMBER_OF_PARTY');
    });
  });

  describe('ReportResponse', () => {
    it('has disclaimer field', () => {
      const r: ReportResponse = {
        format: 'markdown',
        content: '# Report',
        generated_at: '2024-01-01',
        disclaimer: 'CC0-1.0',
      };
      expect(r.disclaimer).toBeTruthy();
    });
  });

  describe('SearchResult', () => {
    it('includes source in member results', () => {
      const sr: SearchResult = {
        members: [
          {
            id: 'p1',
            canonical_name: 'Person',
            display_name: 'Person',
            committee_tags: [],
            source: 'uscl',
          },
        ],
        organizations: [],
        events: [],
        total_count: 1,
      };
      expect(sr.members[0].source).toBe('uscl');
    });
  });

  describe('MemberProfileResponse', () => {
    it('has all required Wikipedia profile fields', () => {
      const p: MemberProfileResponse = {
        member_id: 'test-1',
        bioguide_id: 'T000001',
        wikipedia_title: 'Test Person',
        wikipedia_url: 'https://en.wikipedia.org/wiki/Test_Person',
        wikidata_qid: 'Q12345',
        image_url: 'https://example.com/photo.jpg',
        short_summary: 'A test person.',
        birth_date: '1970-01-01',
        birth_place: 'Test City, USA',
        education: [{ institution: 'Test University' }],
        occupations: ['Politician'],
        career_highlights: [],
        prior_positions: [{ position: 'Mayor' }],
        military_service: [],
        employers: [],
        profile_status: 'available',
        parsed_fields: ['short_summary', 'birth_date', 'education', 'occupations'],
        missing_fields: ['employers', 'military_service'],
        source: 'wikipedia',
        source_reliability: 'external_open_content',
        last_updated: '2026-06-18T00:00:00Z',
        profile_sources: { wikipedia_title: 'Test Person' },
      };
      expect(p.source).toBe('wikipedia');
      expect(p.source_reliability).toBe('external_open_content');
      expect(p.education).toHaveLength(1);
      expect(p.occupations).toContain('Politician');
    });

    it('allows empty arrays for optional fields', () => {
      const p: MemberProfileResponse = {
        member_id: 'test-2',
        source: 'wikipedia',
        source_reliability: 'external_open_content',
        education: [],
        occupations: [],
        career_highlights: [],
        prior_positions: [],
        military_service: [],
        employers: [],
        profile_status: 'summary_only',
        parsed_fields: [],
        missing_fields: [],
        profile_sources: {},
      };
      expect(p.education).toEqual([]);
      expect(p.career_highlights).toEqual([]);
    });

    it('has no prediction or risk fields', () => {
      const p: MemberProfileResponse = {
        member_id: 'test-3',
        source: 'wikipedia',
        source_reliability: 'external_open_content',
        education: [],
        occupations: [],
        career_highlights: [],
        prior_positions: [],
        military_service: [],
        employers: [],
        profile_status: 'summary_only',
        parsed_fields: [],
        missing_fields: [],
        profile_sources: {},
      };
      expect((p as unknown as Record<string, unknown>).risk_score).toBeUndefined();
      expect((p as unknown as Record<string, unknown>).prediction).toBeUndefined();
      expect((p as unknown as Record<string, unknown>).conflict_of_interest).toBeUndefined();
    });
  });

});
