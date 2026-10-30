import { usePrefs } from '../context/PrefsContext';
import { ENVIRONMENTS, PROVIDERS, RANGES, RESOURCE_TYPES } from '../utils/constants';
import { Segmented } from './ui';

/**
 * Shared filter bar (provider, environment, resource type, date range).
 * `custom` enables an explicit start/end date picker (Cost Explorer, Reports).
 */
export default function FilterBar({ custom = false, ranges = RANGES.slice(0, 3) }) {
  const { filters, setFilters, resetFilters } = usePrefs();
  const usingCustom = Boolean(filters.start && filters.end);
  return (
    <section className="filter-bar" aria-label="Filters">
      <div className="field">
        <span className="label">Cloud provider</span>
        <Segmented
          label="Cloud provider"
          value={filters.provider}
          onChange={(v) => setFilters({ provider: v })}
          options={[{ value: 'all', label: 'All' }, ...PROVIDERS.map((p) => ({ value: p.value, label: p.label }))]}
        />
      </div>
      <div className="field">
        <label className="label" htmlFor="f-env">Environment</label>
        <select id="f-env" className="select" value={filters.environment} onChange={(e) => setFilters({ environment: e.target.value })}>
          <option value="all">All environments</option>
          {ENVIRONMENTS.map((e) => (
            <option key={e.value} value={e.value}>{e.label}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label className="label" htmlFor="f-type">Resource type</label>
        <select id="f-type" className="select" value={filters.resource_type} onChange={(e) => setFilters({ resource_type: e.target.value })}>
          <option value="all">All resource types</option>
          {RESOURCE_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <span className="label">Date range</span>
        <Segmented
          label="Date range"
          value={usingCustom ? 'custom' : filters.days}
          onChange={(v) => (v === 'custom' ? setFilters({ start: filters.start || '', end: filters.end || '' , custom: true }) : setFilters({ days: v, start: '', end: '', custom: false }))}
          options={[...ranges, ...(custom ? [{ value: 'custom', label: 'Custom' }] : [])]}
        />
      </div>
      {custom && (usingCustom || filters.custom) && (
        <>
          <div className="field">
            <label className="label" htmlFor="f-start">From</label>
            <input id="f-start" type="date" className="input" value={filters.start} max={filters.end || undefined} onChange={(e) => setFilters({ start: e.target.value })} />
          </div>
          <div className="field">
            <label className="label" htmlFor="f-end">To</label>
            <input id="f-end" type="date" className="input" value={filters.end} min={filters.start || undefined} onChange={(e) => setFilters({ end: e.target.value })} />
          </div>
        </>
      )}
      <div className="reset">
        <button type="button" className="btn link" onClick={resetFilters}>Reset filters</button>
      </div>
    </section>
  );
}
