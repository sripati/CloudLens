import { describe, expect, it } from 'vitest';
import { compact, convert, money, pct, shortDate, signedPct } from './format';

describe('currency formatting', () => {
  it('converts USD to INR with the configured rate', () => {
    expect(convert(10, 'INR', 84.2)).toBeCloseTo(842);
    expect(convert(10, 'USD', 84.2)).toBe(10);
  });
  it('formats full amounts in both currencies', () => {
    expect(money(1234.4, 'USD', 84.2)).toBe('$1,234');
    expect(money(1000, 'INR', 84.2)).toBe('₹84,200');
  });
  it('uses K/M for USD and K/L/Cr for INR in compact form', () => {
    expect(compact(92400, 'USD')).toBe('$92.4K');
    expect(compact(1_200_000, 'USD')).toBe('$1.20M');
    expect(compact(1000, 'INR', 84.2)).toBe('₹84.2K');
    expect(compact(10_000, 'INR', 84.2)).toBe('₹8.42 L');
    expect(compact(150_000, 'INR', 84.2)).toBe('₹1.26 Cr');
  });
});

describe('percentages and dates', () => {
  it('formats percentages', () => {
    expect(pct(12.345)).toBe('12.3%');
    expect(pct(null)).toBe('–');
    expect(signedPct(4.2)).toBe('▲ 4.2%');
    expect(signedPct(-3)).toBe('▼ 3.0%');
  });
  it('formats short dates', () => {
    expect(shortDate('2026-10-29')).toBe('29 Oct');
  });
});
