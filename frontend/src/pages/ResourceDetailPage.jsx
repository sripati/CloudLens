import { Fragment } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import DateRangePicker from '../components/DateRangePicker';
import Icon from '../components/Icon';
import PageHeader from '../components/PageHeader';
import ChartTooltip from '../components/charts/ChartTooltip';
import UtilizationChart from '../components/charts/UtilizationChart';
import { Card, Empty, ErrorBox, Skeleton, StatusBadge } from '../components/ui';
import { usePrefs } from '../context/PrefsContext';
import { useApi } from '../hooks/useApi';
import { ACTION_LABEL, ENV_LABEL, PROVIDER_LABEL, TYPE_LABEL } from '../utils/constants';
import { DASHBOARD_PRESETS, fmtRange } from '../utils/dates';
import { dateTime, pct, shortDate } from '../utils/format';

export default function ResourceDetailPage() {
  const { id } = useParams();
  const { fmt, fmtCompact, range, bounds, boundsReady, filters, setRange } = usePrefs();
  const { data, error, reload } = useApi(`/resources/${id}`, { start: range.start, end: range.end }, { refreshMs: 60000, enabled: boundsReady });
  const r = data?.resource;
  const metricKeys = data?.metrics?.length ? ['cpu', 'memory', 'storage'].filter((k) => data.metrics.some((m) => m[k] !== null)) : [];

  return (
    <>
      <PageHeader title={r?.name || 'Resource'} subtitle={r ? `${PROVIDER_LABEL[r.provider]} · ${TYPE_LABEL[r.resource_type]} · ${ENV_LABEL[r.environment]} · ${r.region}` : 'Loading…'}>
        <DateRangePicker value={filters.range} resolved={range} bounds={bounds} onChange={setRange} presets={DASHBOARD_PRESETS} align="right" />
        <Link to="/resources" className="btn"><Icon name="back" size={16} /> All resources</Link>
      </PageHeader>
      <ErrorBox error={error} onRetry={reload} />
      {!data ? (
        <Skeleton height={400} />
      ) : (
        <>
          <section className="grid-kpi">
            <div className="card"><div className="label">Cost · {range.preset === 'custom' ? 'selected range' : range.label}</div><div className="num">{fmtCompact(data.cost_total)}</div><div className="tiny">{fmt(data.cost_total / data.period.days)} per day · {data.period.days} days</div></div>
            <div className="card"><div className="label">CPU now</div><div className="num">{pct(r.cpu, 0)}</div><div className="tiny">7-day avg {pct(r.cpu_avg_7d, 0)} · peak {pct(r.cpu_max_7d, 0)}</div></div>
            <div className="card"><div className="label">Memory now</div><div className="num">{pct(r.memory, 0)}</div><div className="tiny">7-day avg {pct(r.mem_avg_7d, 0)}</div></div>
            <div className="card"><div className="label">Status</div><div style={{ margin: '14px 0' }}><StatusBadge status={r.status} /></div><div className="tiny">Last sample {dateTime(r.last_sample_at)}</div></div>
          </section>
          <div className="row-wrap">
            <Card className="flex-2" title="Daily cost" subtitle={fmtRange(data.period.start, data.period.end)}>
              <div style={{ width: '100%', height: 260 }}>
                <ResponsiveContainer>
                  <BarChart data={data.cost_series} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="date" tickFormatter={shortDate} tickLine={false} axisLine={{ stroke: 'var(--border)' }} minTickGap={24} />
                    <YAxis tickFormatter={fmtCompact} tickLine={false} axisLine={false} width={60} />
                    <Tooltip content={<ChartTooltip labelFormatter={shortDate} names={{ cost: 'Cost' }} />} cursor={{ fill: 'var(--surface-2)' }} />
                    <Bar dataKey="cost" fill="var(--accent)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card className="flex-1" title="Details">
              <dl className="kv">
                <dt>Resource ID</dt><dd className="mono">{r.resource_id}</dd>
                <dt>Account</dt><dd className="mono">{r.account_id}</dd>
                <dt>Service</dt><dd>{r.service}</dd>
                <dt>SKU / size</dt><dd>{r.sku || '–'}</dd>
                <dt>State</dt><dd>{r.state}</dd>
                <dt>First seen</dt><dd>{dateTime(data.first_seen_at)}</dd>
                {Object.entries(data.tags).map(([k, v]) => (
                  <Fragment key={k}><dt>tag: {k}</dt><dd>{v}</dd></Fragment>
                ))}
              </dl>
            </Card>
          </div>
          <Card title="Utilization · last 7 days" subtitle="Red line = 80% over-utilization threshold">
            {metricKeys.length ? (
              <UtilizationChart data={data.metrics} keys={metricKeys} names={{ cpu: 'CPU', memory: 'Memory', storage: 'Storage used' }}
                colors={{ cpu: 'var(--accent)', memory: 'var(--aws)', storage: 'var(--gcp)' }} />
            ) : <Empty>This resource type does not report utilization metrics.</Empty>}
          </Card>
          <Card title="Recommendations">
            {data.recommendations.length ? (
              data.recommendations.map((x) => (
                <div className="alert-item" key={x.action}>
                  <span className="badge ok">{ACTION_LABEL[x.action]}</span>
                  <div className="t">Save about {fmt(x.monthly_savings)} per month</div>
                  <div className="tiny" style={{ fontSize: 13 }}>{x.detail}</div>
                </div>
              ))
            ) : <Empty>No optimization needed for this resource.</Empty>}
          </Card>
        </>
      )}
    </>
  );
}
