import { useState } from 'react';
import { api } from '../api/client';
import DateRangePicker from '../components/DateRangePicker';
import Icon from '../components/Icon';
import PageHeader from '../components/PageHeader';
import DonutChart from '../components/charts/DonutChart';
import MonthlyBarChart from '../components/charts/MonthlyBarChart';
import { Card, Empty, ErrorBox, Progress, Skeleton, Toast, pctColor } from '../components/ui';
import { BarList, ProviderLegendRows } from '../components/widgets';
import { usePrefs } from '../context/PrefsContext';
import { useApi } from '../hooks/useApi';
import { ACTION_LABEL, ENV_LABEL, PROVIDER_LABEL, SERIES_COLORS } from '../utils/constants';
import { REPORT_PRESETS, fmtRange, resolveRange } from '../utils/dates';
import { longDate, pct, signedPct } from '../utils/format';

const STORE_KEY = 'cloudlens.reportRange';
const DEFAULT_REPORT_RANGE = { preset: 'this_month', start: '', end: '' };

function loadRange() {
  try {
    const v = JSON.parse(sessionStorage.getItem(STORE_KEY) || 'null');
    return v && typeof v === 'object' && v.preset ? v : DEFAULT_REPORT_RANGE;
  } catch {
    return DEFAULT_REPORT_RANGE;
  }
}

function monthNote(m) {
  if (m.days_covered === m.days_in_month) return 'Month in progress (includes today)';
  return `${fmtRange(m.start, m.end)} · ${m.days_covered} of ${m.days_in_month} days`;
}

export default function ReportsPage() {
  const { fmt, fmtCompact, bounds, boundsReady } = usePrefs();
  const [rangeValue, setRangeValue] = useState(loadRange);
  const [toast, setToast] = useState('');
  const range = resolveRange(rangeValue, bounds);
  const query = { start: range.start, end: range.end };
  const { data, error, reload } = useApi('/reports/summary', query, { enabled: boundsReady });
  const envColors = Object.fromEntries(['production', 'staging', 'development', 'unassigned'].map((k, i) => [k, SERIES_COLORS[i]]));
  const title = range.preset === 'custom' ? 'Custom range' : range.label;

  function changeRange(v) {
    setRangeValue(v);
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify(v));
    } catch {
      /* ignore */
    }
  }

  async function download() {
    try {
      await api.download('/reports/summary.csv', query, `cloudlens_report_${range.start}_to_${range.end}.csv`);
    } catch (e) {
      setToast(e.message);
    }
  }

  const months = data?.monthly?.months || [];
  const keys = data?.monthly?.keys || [];

  return (
    <>
      <PageHeader title="Reports" subtitle="Cost summary for any period: pick a range, review it, then download CSV or print to PDF">
        <DateRangePicker value={rangeValue} resolved={range} bounds={bounds} onChange={changeRange} presets={REPORT_PRESETS} align="right" label="Report period" />
        <button type="button" className="btn" onClick={download} disabled={!data}><Icon name="download" size={16} /> Download CSV</button>
        <button type="button" className="btn" onClick={() => window.print()} disabled={!data}><Icon name="reports" size={16} /> Print / PDF</button>
      </PageHeader>
      <ErrorBox error={error} onRetry={reload} />
      {!data ? <Skeleton height={420} /> : (
        <>
          <p className="sub" style={{ margin: 0 }}>
            <b style={{ color: 'var(--text)' }}>{title}</b> · {fmtRange(data.period.start, data.period.end)} · {data.period.days} days · compared with {fmtRange(data.previous_period.start, data.previous_period.end)}
          </p>
          <section className="grid-kpi">
            <div className="card"><div className="label">Total · {data.period.days} days</div><div className="num">{fmtCompact(data.total)}</div><div className="tiny">{fmt(data.daily_average)} per day on average</div></div>
            <div className="card"><div className="label">Previous period</div><div className="num">{fmtCompact(data.previous_total)}</div>
              <div className="tiny" style={{ color: data.change_pct === null ? 'var(--muted)' : data.change_pct > 0 ? 'var(--warn)' : 'var(--ok)' }}>{signedPct(data.change_pct)} vs {fmtRange(data.previous_period.start, data.previous_period.end)}</div>
              {!data.previous_period.complete && <div className="tiny" style={{ marginTop: 4 }}>Data starts {longDate(data.previous_period.data_from)}, so the previous period is incomplete</div>}</div>
            <div className="card"><div className="label">Budget used</div><div className="num">{pct(data.budget_used_pct, 0)}</div><Progress value={data.budget_used_pct} color={pctColor(data.budget_used_pct)} />
              <div className="tiny" style={{ marginTop: 8 }}>of {fmtCompact(data.budget)} budget for these days ({fmtCompact(data.monthly_budget)}/month)</div></div>
            <div className="card"><div className="label">Potential savings</div><div className="num" style={{ color: 'var(--ok)' }}>{fmtCompact(data.potential_savings)}</div><div className="tiny">per month if recommendations are applied</div></div>
          </section>

            <Card title="Monthly breakdown" subtitle={months.length > 1 ? 'Cost per calendar month in the selected period' : 'The selected period is within one month'}>
              {months.length > 1 && <MonthlyBarChart months={months} keys={keys} height={240} />}
              <div className="table-wrap" style={{ marginTop: months.length > 1 ? 12 : 0 }}>
                <table className="data">
                  <thead><tr><th>Month</th>{keys.map((k) => <th key={k} className="r">{PROVIDER_LABEL[k] || k}</th>)}<th className="r">Total</th><th className="r">Budget used</th><th className="r">Change</th></tr></thead>
                  <tbody>
                    {months.map((m) => (
                      <tr key={m.month}>
                        <td>{m.label}{m.partial && <div className="tiny">{monthNote(m)}</div>}</td>
                        {keys.map((k) => <td key={k} className="r mono">{fmt(m[k] || 0)}</td>)}
                        <td className="r mono" style={{ fontWeight: 600 }}>{fmt(m.total)}</td>
                        <td className="r mono" style={{ color: pctColor(m.budget_used_pct) }}>{pct(m.budget_used_pct, 0)}</td>
                        <td className="r mono" style={{ color: m.change_pct === null ? 'var(--muted)' : m.change_pct > 0 ? 'var(--warn)' : 'var(--ok)' }}>
                          {signedPct(m.change_pct)}{m.change_basis === 'run_rate' && <div className="tiny">run rate</div>}
                        </td>
                      </tr>
                    ))}
                    <tr>
                      <td style={{ fontWeight: 700 }}>Total</td>
                      {keys.map((k) => <td key={k} className="r mono" style={{ fontWeight: 600 }}>{fmt(months.reduce((a, m) => a + (m[k] || 0), 0))}</td>)}
                      <td className="r mono" style={{ fontWeight: 700 }}>{fmt(data.total)}</td>
                      <td className="r mono" style={{ color: pctColor(data.budget_used_pct) }}>{pct(data.budget_used_pct, 0)}</td>
                      <td />
                    </tr>
                  </tbody>
                </table>
              </div>
            </Card>

          <div className="row-wrap">
            <Card className="flex-1" title="By provider"><DonutChart rows={data.by_provider} /><div style={{ marginTop: 12 }}><ProviderLegendRows rows={data.by_provider} /></div></Card>
            <Card className="flex-1" title="By environment"><BarList rows={data.by_environment} labels={ENV_LABEL} colorFor={(k) => envColors[k]} /></Card>
            <Card className="flex-1" title="By resource type"><BarList rows={data.by_resource_type} /></Card>
          </div>
          <div className="row-wrap">
            <Card className="flex-2" title="Top services" subtitle="Change compared with the previous period of the same length">
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>Service</th><th className="r">Cost</th><th className="r">Share</th><th className="r">vs previous</th></tr></thead>
                  <tbody>{data.top_services.map((s) => (
                    <tr key={s.key}><td>{s.key}</td><td className="r mono" style={{ fontWeight: 600 }}>{fmt(s.cost)}</td><td className="r mono">{pct(s.pct)}</td><td className="r mono" style={{ color: (s.change_pct || 0) > 0 ? 'var(--warn)' : 'var(--ok)' }}>{signedPct(s.change_pct)}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            </Card>
            <Card className="flex-1" title="Anomalies in this period">
              {data.anomalies.length ? data.anomalies.slice(0, 12).map((a) => (
                <div className="alert-item" key={a.date + a.provider} style={{ marginBottom: 10 }}>
                  <strong>{PROVIDER_LABEL[a.provider]} · {longDate(a.date)}</strong>
                  <div className="tiny" style={{ fontSize: 13 }}>{fmt(a.cost)} vs baseline {fmt(a.baseline)} ({signedPct(a.change_pct, 0)})</div>
                </div>
              )) : <Empty>No anomalies.</Empty>}
              {data.anomalies.length > 12 && <p className="tiny">+{data.anomalies.length - 12} more in the CSV download</p>}
            </Card>
          </div>
          <Card title="Optimization recommendations" subtitle="Based on the latest 30 days of cost and 7 days of utilization">
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
