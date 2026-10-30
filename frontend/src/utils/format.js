// Currency and number formatting. All amounts arrive from the API in USD;
// they are converted to INR here using the exchange rate from Settings.

export function convert(usd, currency, rate) {
  const v = Number(usd) || 0;
  return currency === 'INR' ? v * (Number(rate) || 0) : v;
}

export function money(usd, currency = 'USD', rate = 84.2, decimals = 0) {
  const v = convert(usd, currency, rate);
  const locale = currency === 'INR' ? 'en-IN' : 'en-US';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(v);
}

// Compact form: $92.4K / $1.20M, or Indian units ₹77.6K / ₹8.54 L / ₹1.20 Cr
export function compact(usd, currency = 'USD', rate = 84.2) {
  const x = convert(usd, currency, rate);
  const sign = x < 0 ? '-' : '';
  const a = Math.abs(x);
  if (currency === 'INR') {
    if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(2)} Cr`;
    if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(2)} L`;
    if (a >= 1e3) return `${sign}₹${(a / 1e3).toFixed(1)}K`;
    return `${sign}₹${Math.round(a)}`;
  }
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(1)}K`;
  return `${sign}$${Math.round(a)}`;
}

export function pct(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return '–';
  return `${Number(v).toFixed(digits)}%`;
}

export function signedPct(v, digits = 1) {
  if (v === null || v === undefined) return '–';
  const arrow = v > 0 ? '▲' : v < 0 ? '▼' : '';
  return `${arrow} ${Math.abs(v).toFixed(digits)}%`.trim();
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function shortDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return `${d} ${MONTHS[m - 1]}`;
}

export function longDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

export function dateTime(iso) {
  if (!iso) return '–';
  const dt = new Date(iso);
  return dt.toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function timeAgo(iso) {
  if (!iso) return '';
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function isoDate(d) {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return z.toISOString().slice(0, 10);
}
