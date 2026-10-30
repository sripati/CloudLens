import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import FilterBar from '../components/FilterBar';
import Icon from '../components/Icon';
import PageHeader from '../components/PageHeader';
import CostTrendChart, { TrendLegend } from '../components/charts/CostTrendChart';
import DonutChart from '../components/charts/DonutChart';
import { Card, ErrorBox, Skeleton, Toast, pctColor } from '../components/ui';
import { AlertList, BarList, KpiCard, ProviderLegendRows, ResourceTable, UtilizationPanel } from '../components/widgets';
import { useAuth } from '../context/AuthContext';
import { filterParams, usePrefs } from '../context/PrefsContext';
import { useApi } from '../hooks/useApi';
import { ENV_LABEL, PROVIDER_LABEL, TYPE_LABEL } from '../utils/constants';
import { dateTime, longDate, shortDate, signedPct } from '../utils/format';

export default function DashboardPage() {
  const { isAdmin } = useAuth();
  const { filters, fmtCompact, fmt, currency, rate, settings } = usePrefs();
  const params = filterParams(filters);
  // refresh every 60 s for the near-real-time view
  const { data, error, loading, reload, updatedAt } = useApi('/dashboard/overview', params, { refreshMs: 60000 });
  const [toast, setToast] = useState('');
  const [syncing, setSyncing] = useState(false);

  const s = data?.summary;
  const days = s?.filters?.days || filters.days;
  const keys = data?.trend?.keys || [];
  const scopeBits = [
    filters.provider === 'all' ? 'All providers' : PROVIDER_LABEL[filters.provider],
    filters.environment === 'all' ? 'all environments' : ENV_LABEL[filters.environment],
    filters.resource_type === 'all' ? 'all resource types' : TYPE_LABEL[filters.resource_type],
  ].join(' · ');
  const budget = s?.budget;
  const dailyBudget = budget?.applies_to_filtered_view && budget?.budget ? budget.budget / (s?.month?.days_in_month || 30) : null;
  const up = (s?.period_change_pct ?? 0) >= 0;

  async function syncNow() {
    setSyncing(true);
    try {
      await api.post('/sync/run', { job: 'manual' });
      setToast('Sync started. The dashboard refreshes in a few seconds.');
      setTimeout(() => reload().finally(() => setSyncing(false)), 4000);
    } catch (e) {
      setToast(e.message);
      setSyncing(false);
    }
  }

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Unified cost and resource view across AWS, Azure and GCP">
        {isAdmin && (
          <button type="button" className="btn primary" onClick={syncNow} disabled={syncing}>
            <Icon name="sync" size={16} strokeWidth={2} />
            {syncing ? 'Syncing…' : 'Sync now'}
          </button>
        )}
      </PageHeader>
      <FilterBar />
      <ErrorBox error={error} onRetry={reload} />

      <section aria-label="Key metrics" className="grid-kpi">
        <KpiCard loading={!s} label={`Total spend · last ${days} days`} value={s && fmtCompact(s.period_total)}
          sub={s && `${signedPct(s.period_change_pct)} vs previous ${days} days`} subColor={up ? 'var(--warn)' : 'var(--ok)'} />
        <KpiCard loading={!s} label={`Month to date · ${new Date().toLocaleString('en', { month: 'short' })}`} value={s && fmtCompact(s.month.mtd)}
          bar={budget?.used_pct ?? 0} barColor={pctColor(budget?.used_pct)}
          sub={s && (budget?.applies_to_filtered_view ? `${Math.round(budget.used_pct)}% of ${fmtCompact(budget.budget)} budget` : `Budget applies to provider scope (${fmtCompact(budget.budget)})`)} />
        <KpiCard loading={!s} label="Forecast · month end" value={s && fmtCompact(s.month.forecast)}
          sub={s && (budget?.applies_to_filtered_view ? `${Math.round(budget.forecast_pct)}% of monthly budget` : `7-day avg ${fmtCompact(s.month.avg_daily_7d)}/day`)}
          subColor={budget?.applies_to_filtered_view ? pctColor(budget?.forecast_pct) : 'var(--muted)'} />
        <KpiCard loading={!s} label="Active alerts" value={s && String(s.alerts.total)}
          sub={s && `${s.alerts.critical} critical · ${s.alerts.warning} warning · ${s.alerts.info} info`} subColor={s?.alerts.critical ? 'var(--crit)' : 'var(--muted)'} />
        <KpiCard loading={!s} label="Potential savings" value={s && fmtCompact(s.savings.monthly_total)}
          sub={s && `per month · ${s.savings.count} recommendation${s.savings.count === 1 ? '' : 's'}`} subColor="var(--ok)" />
      </section>

      <div className="row-wrap">
        <Card className="flex-2" title="Daily cost trend"
          subtitle={data ? `${longDate(data.trend.points[0]?.date)} – ${longDate(data.trend.points.at(-1)?.date)} · ${scopeBits}` : 'Loading…'}
          actions={<TrendLegend keys={keys} showTotal={keys.length > 1} dailyBudget={dailyBudget} anomalies={data?.anomalies} />}>
          {data ? (
            <CostTrendChart data={data.trend.points} keys={keys} showTotal={keys.length > 1} dailyBudget={dailyBudget} anomalies={data.anomalies} />
          ) : (
            <Skeleton height={280} />
          )}
        </Card>
        <Card className="flex-1" title="Spend by provider" subtitle={`Last ${days} days · ${scopeBits}`}>
          {data ? (
            <>
              <DonutChart rows={data.by_provider} />
              <div style={{ marginTop: 12 }}>
                <ProviderLegendRows rows={data.by_provider} />
              </div>
            </>
          ) : (
            <Skeleton height={260} />
          )}
        </Card>
      </div>

      <div className="row-wrap">
        <Card className="flex-third" title="Spend by resource type" subtitle={`Last ${days} days`}>
          {data ? <BarList rows={data.by_resource_type} highlight={filters.resource_type} /> : <Skeleton height={220} />}
        </Card>
        <Card className="flex-third" title="Resource utilization" subtitle="Current CPU and memory · alert threshold 80%">
          {data ? <UtilizationPanel providers={data.utilization.providers} /> : <Skeleton height={220} />}
          {data && (
            <p className="tiny" style={{ marginTop: 14 }}>
              {data.utilization.counts.over_utilized} over-utilized · {data.utilization.counts.idle} idle · {data.utilization.counts.healthy} healthy
            </p>
          )}
        </Card>
        <Card className="flex-third" title="Recent alerts" subtitle="Sent via Alertmanager to Slack / Teams"
          actions={<Link to="/alerts" className="btn link">{isAdmin ? 'Manage rules' : 'View all'}</Link>}>
          {data ? <AlertList events={data.recent_alerts} empty="No alerts have fired yet." /> : <Skeleton height={220} />}
        </Card>
      </div>

      <Card title="Top resources by cost" subtitle={`Cost for the last ${days} days · utilization is the latest CPU sample (storage: capacity used)`}
        actions={<Link to="/resources" className="btn link">View all resources</Link>}>
        <ResourceTable rows={data?.top_resources || []} loading={loading} compact />
      </Card>

      <footer className="footer">
        <span>Data source: {settings?.system?.data_source === 'live' ? 'live cloud APIs' : 'mock data generator'}</span>
        <span>Last refreshed: {updatedAt ? dateTime(updatedAt.toISOString()) : '–'} (auto every 60 s)</span>
        {data?.anomalies?.length ? <span>Latest anomaly: {shortDate(data.anomalies[0].date)} {PROVIDER_LABEL[data.anomalies[0].provider]} ({signedPct(data.anomalies[0].change_pct, 0)})</span> : null}
        <span>{currency === 'INR' ? `1 USD = ₹${Number(rate).toFixed(2)} (Settings)` : `Currency USD · INR at ₹${Number(rate).toFixed(2)}`}</span>
        <span className="sr-only">{fmt(0)}</span>
      </footer>
      <Toast message={toast} onDone={() => setToast('')} />
    </>
  );
}
