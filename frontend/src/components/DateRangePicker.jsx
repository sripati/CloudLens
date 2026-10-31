// Date-range picker: a button that opens a popover with quick presets, a two-month calendar,
// typed From/To fields and validation (no future dates, start <= end, within the data bounds,
// at most `max_range_days`). Presets apply at once; a custom range is confirmed with "Apply".
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  PRESETS, WEEKDAYS, addDays, addMonths, fmtDate, fmtMonthTitle, fmtRange, maxISO, minISO, monthGrid,
  presetRange, spanDays, startOfMonth, validateRange, weekday,
} from '../utils/dates';
import Icon from './Icon';

function CalendarIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4.5" width="18" height="17" rx="2.5" />
      <path d="M3 9.5h18M8 2.5v4M16 2.5v4" />
    </svg>
  );
}

function Chevron({ dir }) {
  const d = dir === 'left' ? 'M15 18l-6-6 6-6' : dir === 'right' ? 'M9 18l6-6-6-6' : 'M6 9l6 6 6-6';
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
  );
}

export default function DateRangePicker({ value, resolved, bounds, onChange, presets, align = 'left', label = 'Date range' }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ start: resolved.start, end: resolved.end });
  const [typed, setTyped] = useState({ start: resolved.start, end: resolved.end });
  const [hover, setHover] = useState(null);
  const [view, setView] = useState(startOfMonth(addMonths(resolved.end, -1)));
  const [focusDate, setFocusDate] = useState(resolved.end);
  const wrapRef = useRef(null);
  const popRef = useRef(null);
  const gridRef = useRef(null);
  const [place, setPlace] = useState(align);
  const moveFocus = useRef(false);
  const dialogId = useId();

  const minMonth = startOfMonth(bounds.min_date);
  const maxMonth = startOfMonth(bounds.today);
  const viewRight = addMonths(view, 1);

  // reset the draft whenever the popover opens
  useEffect(() => {
    if (!open) return;
    setDraft({ start: resolved.start, end: resolved.end });
    setTyped({ start: resolved.start, end: resolved.end });
    setHover(null);
    const left = startOfMonth(addMonths(resolved.end, -1));
    setView(left < minMonth ? minMonth : left);
    setFocusDate(resolved.end);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // open towards the side that has room (the header may wrap, so the trigger can be anywhere)
  useLayoutEffect(() => {
    if (!open || !popRef.current || !wrapRef.current) return;
    const vw = document.documentElement.clientWidth;
    const t = wrapRef.current.getBoundingClientRect();
    const w = popRef.current.offsetWidth;
    const fitsLeft = t.left + w <= vw - 16;
    const fitsRight = t.right - w >= 16;
    if (align === 'right') setPlace(fitsRight ? 'right' : fitsLeft ? 'left' : 'center');
    else setPlace(fitsLeft ? 'left' : fitsRight ? 'right' : 'center');
  }, [open, align]);

  // close on outside click / Escape
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => wrapRef.current && !wrapRef.current.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  // keep keyboard focus on the active day after arrow-key navigation
  useEffect(() => {
    if (!moveFocus.current || !gridRef.current) return;
    moveFocus.current = false;
    gridRef.current.querySelector(`[data-date="${focusDate}"]`)?.focus();
  }, [focusDate, view]);

  const error = useMemo(() => {
    if (draft.start && !draft.end) return null; // still picking
    return validateRange(draft.start, draft.end, bounds);
  }, [draft, bounds]);
  const pickingEnd = Boolean(draft.start && !draft.end);
  const disabled = (d) => d > bounds.today || d < bounds.min_date;

  function pick(d) {
    if (disabled(d)) return;
    let next;
    if (!draft.start || draft.end) next = { start: d, end: null };
    else if (d < draft.start) next = { start: d, end: null };
    else next = { start: draft.start, end: d };
    setDraft(next);
    setTyped({ start: next.start || '', end: next.end || '' });
    setFocusDate(d);
  }

  function applyPreset(key) {
    const r = presetRange(key, bounds);
    if (!r) return;
    onChange({ preset: key, start: '', end: '' });
    setOpen(false);
  }

  function apply() {
    if (!draft.start || !draft.end || error) return;
    onChange({ preset: 'custom', start: draft.start, end: draft.end });
    setOpen(false);
  }

  function onType(field, v) {
    setTyped((t) => ({ ...t, [field]: v }));
    const next = { ...draft, [field]: v || null };
    setDraft(next);
    if (v && /^\d{4}-\d{2}-\d{2}$/.test(v) && v >= bounds.min_date && v <= bounds.today) {
      const left = field === 'start' ? startOfMonth(v) : startOfMonth(addMonths(v, -1));
      setView(left < minMonth ? minMonth : left);
    }
  }

  function onGridKey(e) {
    const steps = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    let next = null;
    if (steps[e.key] !== undefined) next = addDays(focusDate, steps[e.key]);
    else if (e.key === 'PageUp') next = addMonths(focusDate, -1);
    else if (e.key === 'PageDown') next = addMonths(focusDate, 1);
    else if (e.key === 'Home') next = addDays(focusDate, -weekday(focusDate));
    else if (e.key === 'End') next = addDays(focusDate, 6 - weekday(focusDate));
    if (!next) return;
    e.preventDefault();
    next = maxISO(minISO(next, bounds.today), bounds.min_date);
    moveFocus.current = true;
    setFocusDate(next);
    if (next < view) setView(startOfMonth(next));
    else if (next > addDays(addMonths(view, 2), -1)) setView(startOfMonth(addMonths(next, -1)));
  }

  // range shown in the calendar (with hover preview while picking the end date)
  const lo = draft.start;
  const hi = error ? null : pickingEnd && hover && hover >= draft.start ? hover : draft.end;

  function renderMonth(monthISO) {
    const cells = monthGrid(monthISO);
    return (
      <div className="drp-month">
        <div className="drp-month-title" aria-hidden="true">{fmtMonthTitle(monthISO)}</div>
        <div className="drp-grid" role="grid" aria-label={fmtMonthTitle(monthISO)}>
          <div className="drp-row" role="row">
            {WEEKDAYS.map((w) => <span key={w} className="drp-wd" role="columnheader" aria-label={w}>{w}</span>)}
          </div>
          {Array.from({ length: cells.length / 7 }, (_, r) => (
            <div className="drp-row" role="row" key={r}>
              {cells.slice(r * 7, r * 7 + 7).map((d, i) => {
                if (!d) return <span key={`e${i}`} className="drp-day empty" role="gridcell" />;
                const off = disabled(d);
                const isStart = d === lo;
                const isEnd = d === hi;
                const inRange = lo && hi && d > lo && d < hi;
                const cls = ['drp-day', off && 'off', inRange && 'in', (isStart || isEnd) && 'edge', isStart && 'start', isEnd && 'end', d === bounds.today && 'today'].filter(Boolean).join(' ');
                const why = d > bounds.today ? ', future date, unavailable' : d < bounds.min_date ? ', no data, unavailable' : '';
                return (
                  <span role="gridcell" key={d} aria-selected={isStart || isEnd || Boolean(inRange)}>
                    <button
                      type="button"
                      className={cls}
                      data-date={d}
                      disabled={off}
                      tabIndex={d === focusDate ? 0 : -1}
                      aria-label={`${fmtDate(d)}${d === bounds.today ? ', today' : ''}${isStart ? ', start date' : ''}${isEnd ? ', end date' : ''}${why}`}
                      onClick={() => pick(d)}
                      onMouseEnter={() => setHover(d)}
                      onFocus={() => setFocusDate(d)}
                    >
                      {Number(d.slice(8))}
                    </button>
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    );
  }

  const presetList = presets.map((key) => ({ key, label: PRESETS[key].label, r: presetRange(key, bounds) }));
  const days = draft.start && draft.end && !error ? spanDays(draft.start, draft.end) : null;

  return (
    <div className="drp" ref={wrapRef}>
      <button
        type="button"
        className="drp-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? dialogId : undefined}
        aria-label={`${label}: ${resolved.label}, ${fmtRange(resolved.start, resolved.end)}. Change`}
        onClick={() => setOpen((o) => !o)}
      >
        <CalendarIcon />
        <span className="drp-trigger-text">
          <span className="drp-trigger-label">{resolved.preset === 'custom' ? 'Custom range' : resolved.label}</span>
          <span className="drp-trigger-dates">{fmtRange(resolved.start, resolved.end)} · {resolved.days} day{resolved.days === 1 ? '' : 's'}</span>
        </span>
        <Chevron dir="down" />
      </button>

      {open && (
        <div id={dialogId} ref={popRef} className={`drp-pop ${place}`} role="dialog" aria-modal="false" aria-label="Choose a date range">
          <div className="drp-presets" role="listbox" aria-label="Quick ranges">
            {presetList.map(({ key, label: l, r }) => (
              <button
                key={key}
                type="button"
                role="option"
                aria-selected={value?.preset === key}
                className={`drp-preset ${value?.preset === key ? 'active' : ''}`}
                disabled={!r}
                onClick={() => applyPreset(key)}
              >
                <span>{l}</span>
                <span className="drp-preset-dates">{r ? fmtRange(r.start, r.end) : 'No data'}</span>
              </button>
            ))}
          </div>

          <div className="drp-main">
            <div className="drp-nav">
              <button type="button" className="drp-navbtn" aria-label="Previous month" disabled={view <= minMonth} onClick={() => setView(addMonths(view, -1))}>
                <Chevron dir="left" />
              </button>
              <span className="tiny">{pickingEnd ? 'Now pick the end date' : 'Pick a start date, then an end date'}</span>
              <button type="button" className="drp-navbtn" aria-label="Next month" disabled={viewRight >= maxMonth} onClick={() => setView(addMonths(view, 1))}>
                <Chevron dir="right" />
              </button>
            </div>
            <div className="drp-months" ref={gridRef} onKeyDown={onGridKey} onMouseLeave={() => setHover(null)}>
              {renderMonth(view)}
              {renderMonth(viewRight)}
            </div>

            <div className="drp-inputs">
              <div className="field">
                <label className="label" htmlFor={`${dialogId}-from`}>From</label>
                <input id={`${dialogId}-from`} type="date" className="input" value={typed.start || ''} min={bounds.min_date} max={bounds.today}
                  aria-invalid={Boolean(error && /start/i.test(error))} onChange={(e) => onType('start', e.target.value)} />
              </div>
              <div className="field">
                <label className="label" htmlFor={`${dialogId}-to`}>To</label>
                <input id={`${dialogId}-to`} type="date" className="input" value={typed.end || ''} min={draft.start || bounds.min_date} max={bounds.today}
                  aria-invalid={Boolean(error && /end/i.test(error))} onChange={(e) => onType('end', e.target.value)} />
              </div>
            </div>

            <div className="drp-foot">
              <div className="drp-msg" role={error ? 'alert' : 'status'} aria-live="polite">
                {error ? (
                  <span className="drp-error"><Icon name="warning" size={16} /> {error}</span>
                ) : days ? (
                  <span>{fmtRange(draft.start, draft.end)} · <b>{days} day{days === 1 ? '' : 's'}</b></span>
                ) : (
                  <span className="tiny">Data available {fmtRange(bounds.min_date, bounds.today)}</span>
                )}
              </div>
              <div className="drp-actions">
                <button type="button" className="btn small" onClick={() => setOpen(false)}>Cancel</button>
                <button type="button" className="btn small primary" disabled={!draft.start || !draft.end || Boolean(error)} onClick={apply}>Apply</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
