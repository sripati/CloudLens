import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

/**
 * Fetch `path` with `params`; refetches when they change and optionally every `refreshMs`
 * (used for the near-real-time dashboard). Keeps showing the previous data while refreshing.
 */
export function useApi(path, params, { refreshMs = 0, enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [updatedAt, setUpdatedAt] = useState(null);
  const key = JSON.stringify([path, params]);
  const seq = useRef(0);

  const load = useCallback(() => {
    if (!enabled || !path) return Promise.resolve();
    const my = ++seq.current;
    setLoading(true);
    return api
      .get(path, params)
      .then((d) => {
        if (my === seq.current) {
          setData(d);
          setError(null);
          setUpdatedAt(new Date());
        }
      })
      .catch((e) => my === seq.current && setError(e))
      .finally(() => my === seq.current && setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);

  useEffect(() => {
    load();
    if (!refreshMs) return undefined;
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') load();
    }, refreshMs);
    return () => clearInterval(id);
  }, [load, refreshMs]);

  return { data, error, loading, reload: load, updatedAt };
}
