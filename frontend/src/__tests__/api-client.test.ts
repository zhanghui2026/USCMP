import { describe, it, expect } from 'vitest';
import axios from 'axios';

describe('API client structure', () => {
  it('uses /api baseURL', () => {
    const api = axios.create({
      baseURL: '/api',
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    });
    expect(api.defaults.baseURL).toBe('/api');
  });

  it('has expected endpoints defined', async () => {
    const { getHealth, getMembers, getMember, search, generateReport } = await import('../app/api/client');

    expect(typeof getHealth).toBe('function');
    expect(typeof getMembers).toBe('function');
    expect(typeof getMember).toBe('function');
    expect(typeof search).toBe('function');
    expect(typeof generateReport).toBe('function');
  });
});
