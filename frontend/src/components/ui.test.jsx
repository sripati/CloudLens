import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Progress, Segmented, StatusBadge, pctColor } from './ui';

describe('UI primitives', () => {
  it('Segmented marks the active option and reports clicks', () => {
    const onChange = vi.fn();
    render(<Segmented label="Currency" value="USD" onChange={onChange} options={[{ value: 'USD', label: 'USD' }, { value: 'INR', label: 'INR' }]} />);
    expect(screen.getByRole('button', { name: 'USD' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'INR' }));
    expect(onChange).toHaveBeenCalledWith('INR');
  });

  it('Progress clamps values to 0-100', () => {
    render(<Progress value={140} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
  });

  it('StatusBadge shows readable labels', () => {
    render(<StatusBadge status="over_utilized" />);
    expect(screen.getByText('Over-utilized')).toBeInTheDocument();
  });

  it('budget colour thresholds', () => {
    expect(pctColor(50)).toBe('var(--ok)');
    expect(pctColor(85)).toBe('var(--warn)');
    expect(pctColor(120)).toBe('var(--crit)');
  });
});
