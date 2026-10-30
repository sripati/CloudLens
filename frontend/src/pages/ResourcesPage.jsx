import { useEffect, useState } from 'react';
import FilterBar from '../components/FilterBar';
import PageHeader from '../components/PageHeader';
import UtilizationChart from '../components/charts/UtilizationChart';
import { Card, Empty, ErrorBox, Segmented, Skeleton } from '../components/ui';
import { ResourceTable } from '../components/widgets';
import { filterParams, usePrefs } from '../context/PrefsContext';
import { useApi } from '../hooks/useApi';
import { ACTION_LABEL, ENV_LABEL, PROVIDER_LABEL } from '../utils/constants';

const STATUSES = [
  { value: '', label: 'All' },
  { value: 'over_utilized', label: 'Over-utilized' },
  { value: 'idle', label: 'Idle' },
  { value: 'healthy', label: 'Healthy' },
  { value: 'no_metrics', label: 'No metrics' },
];

export default function ResourcesPage() {
  const { filters, fmt, fmtCompact } = usePrefs();
  const params = filterParams(filters);
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [sort, setSort] = useState('cost');
  const [hours, setHours] = useState(168);
  useEffect(() => {
    const id = setTimeout(() => setQ(search), 300);
    return () => clearTimeout(id);
  }, [search]);
  const list = useApi('/resources', { ...params, search: q, status, sort }, { refreshMs: 60000 });
  const util = useApi('/resources/utilization', { ...params, hours }, { refreshMs: 60000 });
  const recs = useApi('/resources/recommendations', params);
  const counts = util.data?.counts;
  const keys = [...new Set((util.data?.trend || []).flatMap((p) => Object.keys(p).filter((k) => k !== 'ts')))];

  return (
    <>
      <PageHeader title="Resources" subtitle="Inventory, utilization and optimization across all clouds" />
      <FilterBar />
      <ErrorBox error={list.error || util.error} onRetry={list.reload} />

      <section className="grid-kpi" aria-label="Resource counts">
        {[
          ['Tracked resources', counts?.total, 'var(--muted)', 'across providers in scope'],
          ['Over-utilized', counts?.over_utilized, 'var(--crit)', 'latest CPU ≥ 80%'],
          ['Idle', counts?.idle, 'var(--warn)', '7-day avg CPU below 10%'],
          ['Healthy rate', util.data?.healthy_rate_pct != null ? `${util.data.healthy_rate_pct}%` : '–', 'var(--ok)', 'of measured resources'],
          ['Potential savings', recs.data ? fmtCompact(recs.data.total_monthly_savings) : '–', 'var(--ok)', 'per month'],
        ].map(([label, value, color, sub]) => (
          <div className="card" key={label}>
            <div className="label">{label}</div>
            <div className="num">{value ?? '–'}</div>
            <div style={{ fontSize: 13, color }}>{sub}</div>
          </div>
        ))}
      </section>

      <Card title="CPU utilization trend" subtitle={`Average CPU per provider · ${util.data?.bucket_hours || 1}-hour buckets · red line = 80% threshold`}
        actions={<Segmented label="Window" value={hours} onChange={setHours} options={[{ value: 24, label: '24H' }, { value: 72, label: '3D' }, { value: 168, label: '7D' }]} />}>
        {util.data ? (util.data.trend.length ? <UtilizationChart data={util.data.trend} keys={keys} /> : <Empty>No samples in this window.</Empty>) : <Skeleton height={260} />}
      </Card>

      <Card title="Resource inventory" subtitle="Select a row to drill down into cost and utilization"
        actions={
          <div className="toolbar">
            <label className="sr-only" htmlFor="res-search">Search resources</label>
            <input id="res-search" className="input" placeholder="Search name or ID" value={search} onChange={(e) => setSearch(e.target.value)} />
            <Segmented label="Status" value={status} onChange={setStatus} options={STATUSES} />
            <label className="sr-only" htmlFor="res-sort">Sort</label>
            <select id="res-sort" className="select" style={{ minWidth: 140 }} value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="cost">Sort by cost</option>
              <option value="cpu">Sort by CPU</option>
              <option value="name">Sort by name</option>
            </select>
          </div>
        }>
        <ResourceTable rows={list.data || []} loading={list.loading} />
      </Card>

      <Card title="Cost optimization recommendations" subtitle="Rule-based: idle, under-utilized, non-production running 24x7, low storage usage">
        {recs.data ? (
          recs.data.items.length ? (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Resource</th><th>Provider</th><th>Environment</th><th>Action</th><th>Why</th><th className="r">Monthly cost</th><th className="r">Est. savings</th></tr></thead>
                <tbody>
                  {recs.data.items.map((r) => (
                    <tr key={r.resource_pk}>
                      <td className="mono" style={{ fontWeight: 600 }}>{r.resource}</td>
                      <td>{PROVIDER_LABEL[r.provider]}</td>
                      <td>{ENV_LABEL[r.environment]}</td>
                      <td><span className="badge ok">{ACTION_LABEL[r.action]}</span></td>
                      <td style={{ whiteSpace: 'normal', minWidth: 260 }}>{r.detail}</td>
                      <td className="r mono">{fmt(r.monthly_cost)}</td>
                      <td className="r mono" style={{ color: 'var(--ok)', fontWeight: 600 }}>{fmt(r.monthly_savings)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <Empty>No recommendations. Resources look right-sized.</Empty>
        ) : <Skeleton height={200} />}
      </Card>
    </>
  );
}
