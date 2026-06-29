import { describe, it, expect } from 'vitest';
import { sanitizeGraphLabel } from '../app/components/GraphCanvas/GraphCanvas';

describe('sanitizeGraphLabel', () => {
  it('returns "Unknown" for null', () => {
    expect(sanitizeGraphLabel(null)).toBe('Unknown');
  });

  it('returns "Unknown" for undefined', () => {
    expect(sanitizeGraphLabel(undefined)).toBe('Unknown');
  });

  it('returns "(list)" for arrays', () => {
    expect(sanitizeGraphLabel(['a', 'b'])).toBe('(list)');
  });

  it('returns "(data)" for objects', () => {
    expect(sanitizeGraphLabel({ key: 'val' })).toBe('(data)');
  });

  it('returns string as-is when short enough', () => {
    expect(sanitizeGraphLabel('Mark Warner')).toBe('Mark Warner');
  });

  it('truncates text longer than 30 chars', () => {
    const result = sanitizeGraphLabel(
      'Speaker of the U.S. House of Representatives (2007-2011, 2019-2023)'
    );
    expect(result.length).toBeLessThanOrEqual(31); // 28 + "..."
    expect(result).toContain('...');
  });

  it('replaces newlines with spaces', () => {
    expect(sanitizeGraphLabel('line1\nline2')).toBe('line1 line2');
  });

  it('collapses multiple whitespace', () => {
    expect(sanitizeGraphLabel('hello   world')).toBe('hello world');
  });

  it('deals with empty string', () => {
    expect(sanitizeGraphLabel('')).toBe('Unknown');
  });

  it('does not show large summary text as label', () => {
    const long = 'a'.repeat(500);
    const result = sanitizeGraphLabel(long);
    expect(result.length).toBeLessThanOrEqual(31);
    expect(result).toContain('...');
  });

  it('handles number input', () => {
    expect(sanitizeGraphLabel(42)).toBe('42');
  });

  it('handles boolean input', () => {
    expect(sanitizeGraphLabel(true)).toBe('true');
  });
});
