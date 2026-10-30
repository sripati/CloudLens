import { useState } from 'react';
import { api } from '../api/client';
import FilterBar from '../components/FilterBar';
import Icon from '../components/Icon';
import PageHeader from '../components/PageHeader';
import CostTrendChart, { TrendLegend } from '../components/charts/CostTrendChart';
import MonthlyBarChart from '../components/charts/MonthlyBarChart';
import { Card, Empty, ErrorBox, Segmented, Skeleton, Toast } from '../components/ui';
import { filterParams, usePrefs } from '../context/PrefsContext';
import { useApi } from '../hooks/useApi';
import { ENV_LABEL, PROVIDER_LABEL, RANGES, TYPE_LABEL } from '../utils/constants';
import { longDate, pct, signedPct } from '../utils/format';

const GROUPS = [
  { value: 'provider', label: 'Provider' },
  { value: 'environment', label: 'Environment' },
  { value: 'resource_type', label: 'Resource type' },
  { value: 'none', label: 'Total' },
];
const DIMS = [
  { value: 'service', label: 'Service' },
  { value: 'provider', label: 'Provider' },
  { value: 'environment', label: 'Environment' },
  { value: 'resource_type', label: 'Resource type' },
  { value: 'region', label: 'Region' },
  { value: 'account', label: 'Account' },
];
const LABELS = { ...PROVIDER_LABEL, ...ENV_LABEL, ...TYPE_LABEL };

export default function CostExplorerPage() {
  const { filters, fmt, fmtCompact } = usePrefs();
  const params = filterParams(filters);
  const [groupBy, setGroupBy] = useState('provider');
  const [dim, setDim] = useState('service');
  const [months, setMonths] = useState(6);
  const [toast, setToast] = useState('');
  const daily = useApi('/costs/daily', { ...params, group_by: groupBy });
  const monthly = useApi('/costs/monthly', { ...params, months, group_by: 'provider' });
  const breakdown = useApi('/costs/breakdown', { ...params, dimension: dim, limit: 25 });
  const anomalies = useApi('/costs/anomalies', params);

  const points = daily.data?.points || [];
  const keys = groupBy === 'none' ? [] : daily.data?.keys || [];
  const total = points.reduce((a, p) => a + p.total, 0);
  const peak = points.reduce((m, p) => (p.total > (m?.total ?? -1) ? p : m), null);

  async function exportCsv() {
    try {
      await api.download('/costs/export', params, `cloudlens_costs_${points[0]?.date}_${points.at(-1)?.date}.csv`);
    } catch (e) {
      setToast(e.message);
    }
  }

  return (
    <>
      <PageHeader title="Cost Explorer" subtitle="Historical trends, month-over-month changes and drill-down by any dimension">
        <button type="button" className="btn" onClick={exportCsv}>
          <Icon name="download" size={16} /> Export CSV
        </button>
      </PageHeader>
      <FilterBar custom ranges={RANGES} />
      <ErrorBox error={daily.error || monthly.error || breakdown.error} onRetry={daily.reload} />

      <section className="grid-kpi" aria-label="Period metrics">
        <div className="card"><div className="label">Total in range</div><div className="num">{fmtCompact(total)}</div><div className="tiny">{points.length} days</div></div>
        <div className="card"><div className="label">Daily average</div><div className="num">{fmtCompact(points.length ? total / points.length : 0)}</div><div className="tiny">7-day moving average shown in chart</div></div>
        <div className="card"><div className="label">Peak day</div><div className="num">{peak ? fmtCompact(peak.total) : '–'}</div><div className="tiny">{peak ? longDate(peak.date) : ''}</div></div>
        <div className="card"><div className="label">Anomalies detected</div><div className="num">{anomalies.data ? anomalies.data.length : '–'}</div><div className="tiny">Days &gt;40% above 7-day baseline</div></div>
      </section>

      <Card title="Daily cost" subtitle="Grouped series with 7-day moving average"
        actions={<Segmented label="Group by" value={groupBy} onChange={setGroupBy} options={GROUPS} />}>
        <div style={{ marginBottom: 10 }}>
          <TrendLegend keys={keys.slice(0, 8)} showTotal showMA anomalies={anomalies.data} />
        </div>
        {daily.data ? <CostTrendChart data={points} keys={keys.slice(0, 8)} showTotal showMA anomalies={groupBy === 'provider' ? anomalies.data || [] : []} height={320} /> : <Skeleton height={320} />}
      </Card>

      <div className="row-wrap">
        <Card className="flex-2" title="Monthly cost by provider" subtitle="Current month is partial; month-over-month compares full months"
          actions={<Segmented label="Months" value={months} onChange={setMonths} options={[{ value: 3, label: '3M' }, { value: 6, label: '6M' }, { value: 12, label: '12M' }]} />}>
          {monthly.data ? <MonthlyBarChart months={monthly.data.months} keys={monthly.data.keys} /> : <Skeleton height={280} />}
        </Card>
        <Card className="flex-1" title="Month-over-month" subtitle="Change vs previous month">
          {monthly.data ? (
            <div className="table-wrap">
              <table className="data" style={{ minWidth: 0 }}>
                <thead><tr><th>Month</th><th className="r">Total</th><th className="r">Change</th></tr></thead>
                <tbody>
                  {[...monthly.data.months].reverse().map((m) => {
                    const ch = m.partial ? m.run_rate_change_pct : m.change_pct;
                    return (
                      <tr key={m.month}>
                        <td>{m.label}{m.partial && <span className="tiny"> (to date)</span>}</td>
                        <td className="r mono">{fmtCompact(m.total)}</td>
                        <td className="r mono" style={{ color: ch > 0 ? 'var(--warn)' : 'var(--ok)' }}>
                          {ch === null || ch === undefined ? '–' : signedPct(ch)}{m.partial && ch !== undefined && ch !== null ? <span className="tiny"> run-rate</span> : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : <Skeleton height={240} />}
        </Card>
      </div>

      <div className="row-wrap">
        <Card className="flex-2" title="Cost breakdown" subtitle="Compared with the previous period of equal length"
          actions={
            <select className="select" aria-label="Breakdown dimension" value={dim} onChange={(e) => setDim(e.target.value)}>
              {DIMS.map((d) => <option key={d.value} value={d.value}>By {d.label.toLowerCase()}</option>)}
            </select>
          }>
          {breakdown.data ? (
            breakdown.data.rows.length ? (
              <div className="table-wrap">
                <table className="data" style={{ minWidth: 0 }}>
                  <thead><tr><th>{DIMS.find((d) => d.value === dim)?.label}</th><th className="r">Cost</th><th className="r">Share</th><th className="r">Previous</th><th className="r">Change</th></tr></thead>
                  <tbody>
                    {breakdown.data.rows.slice(0, 15).map((r) => (
                      <tr key={r.key}>
                        <td style={{ whiteSpace: 'normal' }}>{LABELS[r.key] || r.key}</td>
                        <td className="r mono" style={{ fontWeight: 600 }}>{fmt(r.cost)}</td>
                        <td className="r mono">{pct(r.pct)}</td>
                        <td className="r mono muted">{fmt(r.previous)}</td>
                        <td className="r mono" style={{ color: (r.change_pct || 0) > 0 ? 'var(--warn)' : 'var(--ok)' }}>{signedPct(r.change_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <Empty>No costs in this range.</Empty>
          ) : <Skeleton height={240} />}
        </Card>
        <Card className="flex-1" title="Cost anomalies" subtitle="Days more than 40% above the trailing 7-day average">
          {anomalies.data ? (
            anomalies.data.length ? (
              <div className="stack">
                {anomalies.data.slice(0, 8).map((a) => (
                  <div className="alert-item" key={a.date + a.provider}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><strong>{PROVIDER_LABEL[a.provider]} · {longDate(a.date)}</strong><span style={{ color: 'var(--crit)' }} className="mono">{signedPct(a.change_pct, 0)}</span></div>
                    <div className="tiny" style={{ fontSize: 13 }}>{fmt(a.cost)} vs baseline {fmt(a.baseline)}</div>
                  </div>
                ))}
              </div>
            ) : <Empty>No anomalies in this range.</Empty>
          ) : <Skeleton height={200} />}
        </Card>
      </div>
      <Toast message={toast} onDone={() => setToast('')} />
    </>
  );
}
