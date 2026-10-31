// Calendar-date helpers for the date-range picker.
// Dates are handled as 'YYYY-MM-DD' strings (no time, no timezone) so a range never shifts by a day.
// "today" always comes from the server (/costs/date-bounds) when available.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
export const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
export const MAX_RANGE_DAYS = 731;
const ISO_RE = /^\d{4}-\d{2}-\d{2}$/;

const pad = (n) => String(n).padStart(2, '0');

export function isISODate(s) {
  if (typeof s !== 'string' || !ISO_RE.test(s)) return false;
  const [y, m, d] = s.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d;
}

export function parts(s) {
  const [y, m, d] = s.split('-').map(Number);
  return { y, m, d };
}

export function iso(y, m, d) {
  // m is 1-based; normalises overflow (e.g. day 0 = last day of previous month)
  const dt = new Date(Date.UTC(y, m - 1, d));
  return `${dt.getUTCFullYear()}-${pad(dt.getUTCMonth() + 1)}-${pad(dt.getUTCDate())}`;
}

export function todayLocal() {
  const n = new Date();
  return iso(n.getFullYear(), n.getMonth() + 1, n.getDate());
}

export function addDays(s, n) {
  const { y, m, d } = parts(s);
  return iso(y, m, d + n);
}

export function daysInMonth(y, m) {
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

export function addMonths(s, n) {
  const { y, m, d } = parts(s);
  const first = iso(y, m + n, 1);
  const p = parts(first);
  return iso(p.y, p.m, Math.min(d, daysInMonth(p.y, p.m)));
}

export function startOfMonth(s) {
  const { y, m } = parts(s);
  return iso(y, m, 1);
}

export function endOfMonth(s) {
  const { y, m } = parts(s);
  return iso(y, m, daysInMonth(y, m));
}

/** Number of days from a to b inclusive (a <= b gives >= 1). */
export function spanDays(a, b) {
  const pa = parts(a);
  const pb = parts(b);
  return Math.round((Date.UTC(pb.y, pb.m - 1, pb.d) - Date.UTC(pa.y, pa.m - 1, pa.d)) / 86400000) + 1;
}

export const minISO = (a, b) => (a <= b ? a : b);
export const maxISO = (a, b) => (a >= b ? a : b);

export function weekday(s) {
  const { y, m, d } = parts(s);
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay();
}

export function fmtDate(s, withYear = true) {
  if (!s) return '';
  const { y, m, d } = parts(s);
  return withYear ? `${d} ${MONTHS[m - 1]} ${y}` : `${d} ${MONTHS[m - 1]}`;
}

export function fmtMonthTitle(s) {
  const { y, m } = parts(s);
  return `${MONTHS_LONG[m - 1]} ${y}`;
}

export function fmtRange(start, end) {
  if (!start || !end) return '';
  if (start === end) return fmtDate(start);
  const a = parts(start);
  const b = parts(end);
  return a.y === b.y ? `${fmtDate(start, false)} – ${fmtDate(end)}` : `${fmtDate(start)} – ${fmtDate(end)}`;
}

/** 6 x 7 grid of ISO dates for the month containing `monthISO` (null = padding cell). */
export function monthGrid(monthISO) {
  const first = startOfMonth(monthISO);
  const { y, m } = parts(first);
  const lead = weekday(first);
  const total = daysInMonth(y, m);
  const cells = [];
  for (let i = 0; i < lead; i++) cells.push(null);
  for (let d = 1; d <= total; d++) cells.push(iso(y, m, d));
  while (cells.length % 7) cells.push(null);
  return cells;
}

// ---------------------------------------------------------------- presets (always relative to today)
const calendarMonths = (n) => (today) => ({ start: startOfMonth(addMonths(today, -(n - 1))), end: today });

export const PRESETS = {
  last_7_days: { label: 'Last 7 days', range: (t) => ({ start: addDays(t, -6), end: t }) },
  last_30_days: { label: 'Last 30 days', range: (t) => ({ start: addDays(t, -29), end: t }) },
  last_90_days: { label: 'Last 90 days', range: (t) => ({ start: addDays(t, -89), end: t }) },
  this_month: { label: 'This month', range: (t) => ({ start: startOfMonth(t), end: t }) },
  last_month: {
    label: 'Last month',
    range: (t) => {
      const prev = addMonths(startOfMonth(t), -1);
      return { start: prev, end: endOfMonth(prev) };
    },
  },
  last_3_months: { label: 'Last 3 months', range: calendarMonths(3) },
  last_6_months: { label: 'Last 6 months', range: calendarMonths(6) },
  year_to_date: { label: 'Year to date', range: (t) => ({ start: `${parts(t).y}-01-01`, end: t }) },
  last_12_months: { label: 'Last 12 months', range: calendarMonths(12) },
};

export const DASHBOARD_PRESETS = ['last_7_days', 'last_30_days', 'last_90_days', 'this_month', 'last_month', 'last_3_months', 'last_6_months', 'year_to_date', 'last_12_months'];

export function defaultBounds() {
  const today = todayLocal();
  return { today, min_date: addDays(today, -365), max_date: today, max_range_days: MAX_RANGE_DAYS, fallback: true };
}

/** Preset range clamped to the data bounds. Returns null when the preset has no data at all. */
export function presetRange(key, bounds) {
  const p = PRESETS[key];
  if (!p) return null;
  const r = p.range(bounds.today);
  if (r.end < bounds.min_date) return null;
  return { start: maxISO(r.start, bounds.min_date), end: minISO(r.end, bounds.today), clamped: r.start < bounds.min_date };
}

/**
 * Turn the stored range ({preset} or {start, end}) into concrete dates.
 * Relative presets are recomputed every time, so "Last 30 days" never goes stale.
 */
export function resolveRange(range, bounds) {
  if (range?.preset && range.preset !== 'custom') {
    const r = presetRange(range.preset, bounds);
    if (r) return { ...r, preset: range.preset, label: PRESETS[range.preset].label, days: spanDays(r.start, r.end) };
  }
  if (range?.start && range?.end && !validateRange(range.start, range.end, bounds)) {
    return { start: range.start, end: range.end, preset: 'custom', label: fmtRange(range.start, range.end), days: spanDays(range.start, range.end) };
  }
  const r = presetRange('last_30_days', bounds) || { start: bounds.today, end: bounds.today };
  return { ...r, preset: 'last_30_days', label: PRESETS.last_30_days.label, days: spanDays(r.start, r.end) };
}

/**
 * Validation shared with the backend (app/api/deps.py validate_range).
 * Returns null when valid, otherwise a message for the user.
 */
export function validateRange(start, end, bounds) {
  const max = bounds.max_range_days || MAX_RANGE_DAYS;
  if (!start) return 'Choose a start date.';
  if (!isISODate(start)) return 'Start date is not a valid date.';
  if (!end) return 'Choose an end date.';
  if (!isISODate(end)) return 'End date is not a valid date.';
  if (start > bounds.today) return `Start date can’t be in the future. Today is ${fmtDate(bounds.today)}.`;
  if (end > bounds.today) return `End date can’t be in the future. Today is ${fmtDate(bounds.today)}.`;
  if (start > end) return 'Start date must be on or before the end date.';
  if (start < bounds.min_date) return `Data is available from ${fmtDate(bounds.min_date)}. Choose a start date on or after it.`;
  const n = spanDays(start, end);
  if (n > max) return `The range is ${n} days. Choose ${max} days or fewer.`;
  return null;
}
