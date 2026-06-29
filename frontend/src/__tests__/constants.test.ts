import { describe, it, expect } from 'vitest';
import {
  PARTY_COLORS,
  DATA_MODE_COLORS,
  DATA_MODE_LABELS,
  DATA_MODE_TOOLTIPS,
  getPartyColor,
} from '../app/constants';

describe('constants', () => {
  describe('DATA_MODE_COLORS', () => {
    it('has entries for mock, mixed, real, unknown', () => {
      expect(DATA_MODE_COLORS).toHaveProperty('mock');
      expect(DATA_MODE_COLORS).toHaveProperty('mixed');
      expect(DATA_MODE_COLORS).toHaveProperty('real');
      expect(DATA_MODE_COLORS).toHaveProperty('unknown');
    });

    it('mock is orange', () => {
      expect(DATA_MODE_COLORS.mock).toBe('orange');
    });

    it('real is green', () => {
      expect(DATA_MODE_COLORS.real).toBe('green');
    });

    it('mixed is blue', () => {
      expect(DATA_MODE_COLORS.mixed).toBe('blue');
    });
  });

  describe('DATA_MODE_LABELS', () => {
    it('has Chinese labels for each mode', () => {
      expect(DATA_MODE_LABELS.mock).toBe('Mock 数据');
      expect(DATA_MODE_LABELS.mixed).toBe('混合数据');
      expect(DATA_MODE_LABELS.real).toBe('真实数据');
    });
  });

  describe('DATA_MODE_TOOLTIPS', () => {
    it('has tooltips for each mode', () => {
      expect(DATA_MODE_TOOLTIPS.mock).toContain('Mock');
      expect(DATA_MODE_TOOLTIPS.mixed).toContain('Mock');
      expect(DATA_MODE_TOOLTIPS.real).toContain('真实');
    });
  });

  describe('getPartyColor', () => {
    it('returns blue for Democratic', () => {
      expect(getPartyColor('Democratic')).toBe('#1890ff');
    });

    it('returns red for Republican', () => {
      expect(getPartyColor('Republican')).toBe('#f5222d');
    });

    it('returns gray for Independent', () => {
      expect(getPartyColor('Independent')).toBe('#8c8c8c');
    });

    it('returns gray for unknown party', () => {
      expect(getPartyColor('Unknown')).toBe('#8c8c8c');
    });

    it('returns gray for undefined', () => {
      expect(getPartyColor()).toBe('#8c8c8c');
    });
  });
});
