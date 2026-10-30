import { useMemo, useState } from 'react';
import { api } from '../api/client';
import Icon from '../components/Icon';
import PageHeader from '../components/PageHeader';
import DonutChart from '../components/charts/DonutChart';
import { Card, Empty, ErrorBox, Progress, Skeleton, Toast, pctColor } from '../components/ui';
import { BarList, ProviderLegendRows } from '../components/widgets';
import { usePrefs } from '../context/PrefsContext';
import { useApi } from '../hooks/useApi';
import { ACTION_LABEL, ENV_LABEL, PROVIDER_LABEL, SERIES_COLORS } from '../utils/constants';
import { longDate, pct, signedPct } from '../utils/format';

function monthOptions() {
  const out = [];
  const d = new Date();
  d.setDate(1);
  for (let i = 0; i < 6; i++) {
    const v = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    out.push({ value: v, label: d.toLocaleString('en', { month: 'long', year: 'numeric' }) });
    d.setMonth(d.getMonth() - 1);
  }
  return out;
}

export default function ReportsPage() {
  const { fmt, fmtCompact } = usePrefs();
  const months = useMemo(monthOptions, []);
  const [month, setMonth] = useState(months[0].value);
  const [toast, setToast] = useState('');
  const { data, error, reload } = useApi('/reports/monthly', { month });
  const envColors = Object.fromEntries(['production', 'staging', 'development', 'unassigned'].map((k, i) => [k, SERIES_COLORS[i]]));

  async function download() {
    try {
      await api.download('/reports/monthly.csv', { month }, `cloudlens_report_${month}.csv`);
    } catch (e) {
      setToast(e.message);
    }
  }

  return (
    <>
      <PageHeader title="Reports" subtitle="Monthly cost summary for finance and management reviews">
        <label className="sr-only" htmlFor="rep-month">Month</label>
        <select id="rep-month" className="select" value={month} onChange={(e) => setMonth(e.target.value)}>
          {months.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
        <button type="button" className="btn" onClick={download}><Icon name="download" size={16} /> Download CSV</button>
        <button type="button" className="btn" onClick={() => window.print()}><Icon name="reports" size={16} /> Print / PDF</button>
      </PageHeader>
      <ErrorBox error={error} onRetry={reload} />
      {!data ? <Skeleton height={420} /> : (
        <>
          <section className="grid-kpi">
            <div className="card"><div className="label">{data.label}{data.period.complete ? '' : ' · to date'}</div><div className="num">{fmtCompact(data.total)}</div><div className="tiny">{longDate(data.period.start)} – {longDate(data.period.end)}</div></div>
            <div className="card"><div className="label">Previous month</div><div className="num">{fmtCompact(data.previous_month_total)}</div><div className="tiny" style={{ color: (data.change_pct || 0) > 0 ? 'var(--warn)' : 'var(--ok)' }}>{signedPct(data.change_pct)} {data.period.complete ? '' : '(partial month)'}</div></div>
            <div className="card"><div className="label">Budget used</div><div className="num">{pct(data.budget_used_pct, 0)}</div><Progress value={data.budget_used_pct} color={pctColor(data.budget_used_pct)} /><div className="tiny" style={{ marginTop: 8 }}>of {fmtCompact(data.budget)}</div></div>
            <div className="card"><div className="label">Potential savings</div><div className="num" style={{ color: 'var(--ok)' }}>{fmtCompact(data.potential_savings)}</div><div className="tiny">per month if recommendations are applied</div></div>
          </section>
          <div className="row-wrap">
            <Card className="flex-1" title="By provider"><DonutChart rows={data.by_provider} /><div style={{ marginTop: 12 }}><ProviderLegendRows rows={data.by_provider} /></div></Card>
            <Card className="flex-1" title="By environment"><BarList rows={data.by_environment} labels={ENV_LABEL} colorFor={(k) => envColors[k]} /></Card>
            <Card className="flex-1" title="By resource type"><BarList rows={data.by_resource_type} /></Card>
          </div>
          <div className="row-wrap">
            <Card className="flex-2" title="Top services">
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>Service</th><th className="r">Cost</th><th className="r">Share</th><th className="r">vs previous</th></tr></thead>
                  <tbody>{data.top_services.map((s) => (
                    <tr key={s.key}><td>{s.key}</td><td className="r mono" style={{ fontWeight: 600 }}>{fmt(s.cost)}</td><td className="r mono">{pct(s.pct)}</td><td className="r mono" style={{ color: (s.change_pct || 0) > 0 ? 'var(--warn)' : 'var(--ok)' }}>{signedPct(s.change_pct)}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            </Card>
            <Card className="flex-1" title="Anomalies this month">
              {data.anomalies.length ? data.anomalies.map((a) => (
                <div className="alert-item" key={a.date + a.provider} style={{ marginBottom: 10 }}>
                  <strong>{PROVIDER_LABEL[a.provider]} · {longDate(a.date)}</strong>
                  <div className="tiny" style={{ fontSize: 13 }}>{fmt(a.cost)} vs baseline {fmt(a.baseline)} ({signedPct(a.change_pct, 0)})</div>
                </div>
              )) : <Empty>No anomalies.</Empty>}
            </Card>
          </div>
          <Card title="Optimization recommendations">
            {data.recommendations.length ? (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>Resource</th><th>Provider</th><th>Action</th><th>Detail</th><th className="r">Savings / month</th></tr></thead>
                  <tbody>{data.recommendations.map((r) => (
                    <tr key={r.resource_pk}><td className="mono">{r.resource}</td><td>{PROVIDER_LABEL[r.provider]}</td><td>{ACTION_LABEL[r.action]}</td><td style={{ whiteSpace: 'normal' }}>{r.detail}</td><td className="r mono" style={{ color: 'var(--ok)', fontWeight: 600 }}>{fmt(r.monthly_savings)}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            ) : <Empty>No recommendations.</Empty>}
          </Card>
        </>
      )}
      <Toast message={toast} onDone={() => setToast('')} />
    </>
  );
}
