import { usePrefs } from '../context/PrefsContext';
import { ENVIRONMENTS, PROVIDERS, RESOURCE_TYPES } from '../utils/constants';
import { DASHBOARD_PRESETS } from '../utils/dates';
import DateRangePicker from './DateRangePicker';
import { Segmented } from './ui';

/** Shared filter bar (provider, environment, resource type, date range) for Dashboard, Cost Explorer, Resources. */
export default function FilterBar({ presets = DASHBOARD_PRESETS }) {
  const { filters, setFilters, resetFilters, range, bounds, setRange } = usePrefs();
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
        <DateRangePicker value={filters.range} resolved={range} bounds={bounds} onChange={setRange} presets={presets} />
      </div>
      <div className="reset">
        <button type="button" className="btn link" onClick={resetFilters}>Reset filters</button>
      </div>
    </section>
  );
}
