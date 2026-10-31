import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { DASHBOARD_PRESETS, resolveRange } from '../utils/dates';
import DateRangePicker from './DateRangePicker';

const bounds = { today: '2026-10-31', min_date: '2026-05-01', max_date: '2026-10-31', max_range_days: 731 };

function Harness({ onChange = () => {}, initial = { preset: 'last_30_days' } }) {
  const [value, setValue] = useState(initial);
  return (
    <DateRangePicker
      value={value}
      resolved={resolveRange(value, bounds)}
      bounds={bounds}
      presets={DASHBOARD_PRESETS}
      onChange={(v) => { setValue(v); onChange(v); }}
    />
  );
}

const open = () => fireEvent.click(screen.getByRole('button', { name: /Date range: Last 30 days/ }));
const day = (label) => screen.getByRole('button', { name: new RegExp(`^${label}`) });

describe('DateRangePicker', () => {
  it('shows the resolved range on the trigger', () => {
    render(<Harness />);
    expect(screen.getByText('2 Oct – 31 Oct 2026 · 30 days')).toBeInTheDocument();
  });

  it('applies a preset in one click', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    open();
    fireEvent.click(screen.getByRole('option', { name: /Last 6 months/ }));
    expect(onChange).toHaveBeenCalledWith({ preset: 'last_6_months', start: '', end: '' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('picks a custom range by clicking start then end, then applies', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    open();
    fireEvent.click(day('5 Oct 2026'));
    expect(screen.getByText('Now pick the end date')).toBeInTheDocument();
    fireEvent.click(day('12 Oct 2026'));
    expect(screen.getByText(/8 days/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    expect(onChange).toHaveBeenCalledWith({ preset: 'custom', start: '2026-10-05', end: '2026-10-12' });
  });

  it('clicking a day before the start restarts the selection', () => {
    render(<Harness />);
    open();
    fireEvent.click(day('20 Oct 2026'));
    fireEvent.click(day('10 Oct 2026'));
    expect(day('10 Oct 2026')).toHaveAccessibleName(/start date/);
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
  });

  it('disables future dates and dates without data', () => {
    render(<Harness />);
    open();
    const dialog = screen.getByRole('dialog');
    // the right-hand month is October; November is not reachable
    expect(screen.getByRole('button', { name: 'Next month' })).toBeDisabled();
    expect(within(dialog).getByRole('button', { name: /^31 Oct 2026, today/ })).toBeEnabled();
  });

  it('validates typed dates: future end and start after end', () => {
    render(<Harness />);
    open();
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-11-15' } });
    expect(screen.getByRole('alert')).toHaveTextContent('End date can’t be in the future');
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-10-20' } });
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '2026-10-10' } });
    expect(screen.getByRole('alert')).toHaveTextContent('Start date must be on or before the end date');
  });

  it('closes on Escape without changing the value', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    open();
    fireEvent.click(day('5 Oct 2026'));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('supports keyboard navigation in the calendar', () => {
    render(<Harness />);
    open();
    const end = day('31 Oct 2026');
    act(() => end.focus());
    fireEvent.keyDown(end, { key: 'ArrowLeft' });
    expect(document.activeElement).toHaveAttribute('data-date', '2026-10-30');
    fireEvent.keyDown(document.activeElement, { key: 'ArrowUp' });
    expect(document.activeElement).toHaveAttribute('data-date', '2026-10-23');
    fireEvent.keyDown(document.activeElement, { key: 'ArrowRight' });
    fireEvent.keyDown(document.activeElement, { key: 'ArrowDown' });
    fireEvent.keyDown(document.activeElement, { key: 'ArrowDown' });
    expect(document.activeElement).toHaveAttribute('data-date', '2026-10-31'); // never moves into the future
  });
});
