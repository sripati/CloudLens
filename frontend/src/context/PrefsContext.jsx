// User preferences: theme (dark/light), display currency (USD/INR), the shared filter state used by
// Dashboard, Cost Explorer and Resources, and the server's date bounds (today + first date with data).
// Theme/currency persist in localStorage, filters in sessionStorage.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { defaultBounds, resolveRange } from '../utils/dates';
import { compact, money } from '../utils/format';

const PrefsContext = createContext(null);

function load(storage, key, fallback) {
  try {
    const v = storage.getItem(key);
    return v ? JSON.parse(v) : fallback;
  } catch {
    return fallback;
  }
}
function save(storage, key, value) {
  try {
    storage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

// `range` holds either a relative preset ({preset: 'last_30_days'}) or fixed dates ({preset: 'custom', start, end}).
export const DEFAULT_RANGE = { preset: 'last_30_days', start: '', end: '' };
export const DEFAULT_FILTERS = { provider: 'all', environment: 'all', resource_type: 'all', range: DEFAULT_RANGE };

function loadFilters() {
  const stored = load(sessionStorage, 'cloudlens.filters', {});
  const f = { ...DEFAULT_FILTERS, ...stored };
  if (!f.range || typeof f.range !== 'object') f.range = DEFAULT_RANGE; // older format stored `days`
  delete f.days;
  delete f.start;
  delete f.end;
  delete f.custom;
  return f;
}

export function PrefsProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem('cloudlens.theme') || 'dark';
    } catch {
      return 'dark';
    }
  });
  const [currency, setCurrencyState] = useState(() => load(localStorage, 'cloudlens.currency', null));
  const [settings, setSettings] = useState(null);
  const [bounds, setBounds] = useState(null);
  const [filters, setFiltersState] = useState(loadFilters);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('cloudlens.theme', theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  const refreshSettings = useCallback(() => api.get('/settings').then(setSettings).catch(() => {}), []);
  const refreshBounds = useCallback(
    () => api.get('/costs/date-bounds').then(setBounds).catch(() => setBounds((b) => b || defaultBounds())),
    [],
  );

  const setCurrency = useCallback((c) => {
    setCurrencyState(c);
    save(localStorage, 'cloudlens.currency', c);
  }, []);

  const setFilters = useCallback((patch) => {
    setFiltersState((prev) => {
      const next = typeof patch === 'function' ? patch(prev) : { ...prev, ...patch };
      save(sessionStorage, 'cloudlens.filters', next);
      return next;
    });
  }, []);

  const value = useMemo(() => {
    const cur = currency || settings?.default_currency || 'USD';
    const rate = settings?.exchange_rate_inr || 84.2;
    const b = bounds || defaultBounds();
    const range = resolveRange(filters.range, b);
    return {
      theme,
      toggleTheme: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')),
      currency: cur,
      setCurrency,
      rate,
      fmt: (usd, decimals = 0) => money(usd, cur, rate, decimals),
      fmtCompact: (usd) => compact(usd, cur, rate),
      settings,
      refreshSettings,
      bounds: b,
      boundsReady: Boolean(bounds),
      refreshBounds,
      filters,
      range, // resolved: { start, end, preset, label, days }
      filterQuery: {
        provider: filters.provider,
        environment: filters.environment,
        resource_type: filters.resource_type,
        start: range.start,
        end: range.end,
      },
      setFilters,
      setRange: (r) => setFilters({ range: r }),
      resetFilters: () => setFilters({ ...DEFAULT_FILTERS }),
    };
  }, [theme, currency, settings, bounds, setCurrency, refreshSettings, refreshBounds, filters, setFilters]);

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs() {
  return useContext(PrefsContext);
}
