import { describe, expect, it } from 'vitest';
import {
  addMonths, fmtRange, isISODate, monthGrid, presetRange, resolveRange, spanDays, validateRange,
} from './dates';

const bounds = { today: '2026-10-31', min_date: '2025-10-31', max_date: '2026-10-31', max_range_days: 731 };

describe('date helpers', () => {
  it('validates ISO dates strictly', () => {
    expect(isISODate('2026-02-28')).toBe(true);
    expect(isISODate('2026-02-30')).toBe(false);
    expect(isISODate('31/10/2026')).toBe(false);
  });
  it('adds months without overflowing short months', () => {
    expect(addMonths('2026-03-31', -1)).toBe('2026-02-28');
    expect(addMonths('2026-12-15', 1)).toBe('2027-01-15');
  });
  it('counts days inclusively', () => {
    expect(spanDays('2026-10-01', '2026-10-31')).toBe(31);
    expect(spanDays('2026-10-31', '2026-10-31')).toBe(1);
  });
  it('builds a Sunday-first month grid', () => {
    const g = monthGrid('2026-10-15'); // 1 Oct 2026 is a Thursday
    expect(g.slice(0, 5)).toEqual([null, null, null, null, '2026-10-01']);
    expect(g.length % 7).toBe(0);
  });
  it('formats ranges', () => {
    expect(fmtRange('2026-10-01', '2026-10-31')).toBe('1 Oct – 31 Oct 2026');
    expect(fmtRange('2025-12-01', '2026-01-31')).toBe('1 Dec 2025 – 31 Jan 2026');
  });
});

describe('presets are computed from today, not hard-coded', () => {
  it('rolling day ranges end today', () => {
    expect(presetRange('last_7_days', bounds)).toMatchObject({ start: '2026-10-25', end: '2026-10-31' });
    expect(presetRange('last_30_days', bounds)).toMatchObject({ start: '2026-10-02', end: '2026-10-31' });
  });
  it('calendar presets', () => {
    expect(presetRange('this_month', bounds)).toMatchObject({ start: '2026-10-01', end: '2026-10-31' });
    expect(presetRange('last_month', bounds)).toMatchObject({ start: '2026-09-01', end: '2026-09-30' });
    expect(presetRange('last_6_months', bounds)).toMatchObject({ start: '2026-05-01', end: '2026-10-31' });
    expect(presetRange('year_to_date', bounds)).toMatchObject({ start: '2026-01-01', end: '2026-10-31' });
  });
  it('moves with the date', () => {
    const later = { ...bounds, today: '2027-01-05' };
    expect(presetRange('last_month', later)).toMatchObject({ start: '2026-12-01', end: '2026-12-31' });
    expect(presetRange('year_to_date', later)).toMatchObject({ start: '2027-01-01' });
  });
  it('clamps to the first date with data', () => {
    const short = { ...bounds, min_date: '2026-06-15' };
    expect(presetRange('last_6_months', short)).toMatchObject({ start: '2026-06-15', clamped: true });
    expect(presetRange('last_month', { ...bounds, min_date: '2026-10-10' })).toBeNull();
  });
  it('resolves stored values and falls back safely', () => {
    expect(resolveRange({ preset: 'last_7_days' }, bounds)).toMatchObject({ start: '2026-10-25', days: 7, label: 'Last 7 days' });
    expect(resolveRange({ preset: 'custom', start: '2026-09-10', end: '2026-09-20' }, bounds)).toMatchObject({ days: 11, preset: 'custom' });
    // a stored custom range that became invalid (e.g. future) falls back to the last 30 days
    expect(resolveRange({ preset: 'custom', start: '2026-10-01', end: '2026-11-05' }, bounds)).toMatchObject({ preset: 'last_30_days' });
  });
});

describe('range validation', () => {
  it('accepts a valid range and a single day', () => {
    expect(validateRange('2026-10-01', '2026-10-31', bounds)).toBeNull();
    expect(validateRange('2026-10-31', '2026-10-31', bounds)).toBeNull();
  });
  it('rejects future dates', () => {
    expect(validateRange('2026-10-01', '2026-11-01', bounds)).toMatch(/End date can’t be in the future/);
    expect(validateRange('2026-11-02', '2026-11-05', bounds)).toMatch(/Start date can’t be in the future/);
  });
  it('rejects start after end', () => {
    expect(validateRange('2026-10-20', '2026-10-10', bounds)).toMatch(/on or before the end date/);
  });
  it('rejects missing, malformed, too early and too long ranges', () => {
    expect(validateRange('', '2026-10-10', bounds)).toMatch(/start date/);
    expect(validateRange('2026-10-01', '', bounds)).toMatch(/end date/);
    expect(validateRange('2026-02-30', '2026-03-10', bounds)).toMatch(/not a valid date/);
    expect(validateRange('2025-01-01', '2025-12-01', bounds)).toMatch(/Data is available from 31 Oct 2025/);
    expect(validateRange('2024-10-01', '2026-10-31', { ...bounds, min_date: '2020-01-01' })).toMatch(/731 days or fewer/);
  });
});
