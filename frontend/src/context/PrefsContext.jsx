// User preferences: theme (dark/light), display currency (USD/INR) and the shared filter state
// used by Dashboard, Cost Explorer and Resources. Theme/currency persist in localStorage,
// filters in sessionStorage.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
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

export const DEFAULT_FILTERS = { provider: 'all', environment: 'all', resource_type: 'all', days: 30, start: '', end: '' };

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
  const [filters, setFiltersState] = useState(() => ({ ...DEFAULT_FILTERS, ...load(sessionStorage, 'cloudlens.filters', {}) }));

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('cloudlens.theme', theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  const refreshSettings = useCallback(() => api.get('/settings').then(setSettings).catch(() => {}), []);

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
      filters,
      setFilters,
      resetFilters: () => setFilters({ ...DEFAULT_FILTERS }),
    };
  }, [theme, currency, settings, setCurrency, refreshSettings, filters, setFilters]);

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs() {
  return useContext(PrefsContext);
}

// Convert UI filter state into API query params
export function filterParams(f) {
  const p = {
    provider: f.provider,
    environment: f.environment,
    resource_type: f.resource_type,
  };
  if (f.start && f.end) {
    p.start = f.start;
    p.end = f.end;
  } else {
    p.days = f.days;
  }
  return p;
}
