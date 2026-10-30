import { useState } from 'react';
import { api } from '../api/client';
import Icon from '../components/Icon';
import PageHeader from '../components/PageHeader';
import { Badge, Card, ErrorBox, Skeleton, Toast } from '../components/ui';
import { useApi } from '../hooks/useApi';
import { PROVIDERS, PROVIDER_LABEL } from '../utils/constants';
import { dateTime, timeAgo } from '../utils/format';

const API_NAMES = {
  aws: 'Cost Explorer · EC2 · RDS · CloudWatch',
  azure: 'Cost Management · Resource Manager · Monitor',
  gcp: 'Cloud Billing · BigQuery billing export · Cloud Monitoring',
};
const JOB_LABEL = { daily_sync: 'Daily cost sync', intraday_costs: "Today's running cost", metrics: 'Utilization metrics', alert_evaluation: 'Alert evaluation', retention: 'Data retention cleanup' };

export default function CloudAccountsPage() {
  const status = useApi('/sync/status', null, { refreshMs: 15000 });
  const runs = useApi('/sync/runs', { limit: 30 }, { refreshMs: 15000 });
  const [toast, setToast] = useState('');
  const [tests, setTests] = useState({});
  const [anomaly, setAnomaly] = useState({ provider: 'aws', factor: 2.5, days_ago: 1 });
  const isMock = status.data?.data_source === 'mock';

  async function act(fn, msg) {
    try {
      const r = await fn();
      setToast(msg);
      setTimeout(() => { status.reload(); runs.reload(); }, 2500);
      return r;
    } catch (e) {
      setToast(e.message);
      return null;
    }
  }

  return (
    <>
      <PageHeader title="Cloud Accounts" subtitle="Provider connectivity, data source mode, scheduled jobs and sync history" />
      <ErrorBox error={status.error} onRetry={status.reload} />
      {status.data && (
        <div className="notice">
          Data source is <strong className="mono">DATA_SOURCE={status.data.data_source}</strong>.{' '}
          {isMock ? 'The built-in generator supplies realistic data. Set DATA_SOURCE=live and add credentials in .env to use real AWS, Azure and GCP APIs.' : 'Real provider APIs are used. Providers without credentials are skipped.'}
        </div>
      )}
      <div className="row-wrap">
        {(status.data?.providers || PROVIDERS.map((p) => ({ provider: p.value }))).map((p) => {
          const t = tests[p.provider];
          return (
            <Card key={p.provider} className="flex-third" title={PROVIDERS.find((x) => x.value === p.provider)?.name} subtitle={API_NAMES[p.provider]}>
              {!status.data ? <Skeleton height={140} /> : (
                <>
                  <dl className="kv">
                    <dt>Mode</dt><dd><Badge kind={isMock ? 'info' : p.configured ? 'ok' : 'warning'}>{isMock ? 'Mock' : p.configured ? 'Live · credentials set' : 'Live · not configured'}</Badge></dd>
                    <dt>Account</dt><dd className="mono">{p.account_id || '–'}</dd>
                    <dt>Last run</dt><dd>{p.last_run ? <><Badge kind={p.last_run.status}>{p.last_run.status}</Badge> {timeAgo(p.last_run.started_at)}</> : '–'}</dd>
                    <dt>Last success</dt><dd>{dateTime(p.last_success_at)}</dd>
                    {p.last_run?.error && <><dt>Error</dt><dd style={{ color: 'var(--warn)' }}>{p.last_run.error}</dd></>}
                  </dl>
                  {t && <div className={t.ok ? 'notice' : 'error-box'} style={{ marginTop: 12 }}>{t.message}{t.account ? ` · ${t.account}` : ''}</div>}
                  <div className="toolbar" style={{ marginTop: 14 }}>
                    <button type="button" className="btn small" onClick={async () => { const r = await act(() => api.post(`/sync/test/${p.provider}`), 'Connection tested'); if (r) setTests({ ...tests, [p.provider]: r }); }}>Test connection</button>
                    <button type="button" className="btn small primary" onClick={() => act(() => api.post('/sync/run', { job: 'manual', providers: [p.provider] }), `${PROVIDER_LABEL[p.provider]} sync started`)}><Icon name="sync" size={14} /> Sync now</button>
                  </div>
                </>
              )}
            </Card>
          );
        })}
      </div>

      <div className="row-wrap">
        <Card className="flex-1" title="Scheduled jobs" subtitle="APScheduler inside the backend">
          {status.data ? (
            <div className="stack">
              {status.data.jobs.length === 0 && <div className="tiny">Scheduler disabled (SCHEDULER_ENABLED=false)</div>}
              {status.data.jobs.map((j) => (
                <div key={j.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                  <span><strong>{JOB_LABEL[j.id] || j.id}</strong><div className="tiny mono">{j.trigger}</div></span>
                  <span className="tiny">next {dateTime(j.next_run)}</span>
                </div>
              ))}
              <button type="button" className="btn small" style={{ alignSelf: 'flex-start' }} onClick={() => act(() => api.post('/sync/run', { job: 'daily' }), 'Daily sync started for all providers')}>Run daily sync now</button>
            </div>
          ) : <Skeleton height={160} />}
        </Card>
        {isMock && (
          <Card className="flex-1" title="Demo: simulate a cost spike" subtitle="Mock mode only · multiplies one day's cost for a provider so the anomaly and budget alerts fire">
            <div className="form-grid">
              <div className="field"><label className="label" htmlFor="a-p">Provider</label>
                <select id="a-p" className="select" value={anomaly.provider} onChange={(e) => setAnomaly({ ...anomaly, provider: e.target.value })}>{PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}</select></div>
              <div className="field"><label className="label" htmlFor="a-f">Multiplier</label>
                <input id="a-f" type="number" min="1.1" max="10" step="0.1" className="input" value={anomaly.factor} onChange={(e) => setAnomaly({ ...anomaly, factor: Number(e.target.value) })} /></div>
              <div className="field"><label className="label" htmlFor="a-d">Days ago</label>
                <input id="a-d" type="number" min="0" max="30" className="input" value={anomaly.days_ago} onChange={(e) => setAnomaly({ ...anomaly, days_ago: Number(e.target.value) })} /></div>
            </div>
            <div className="toolbar" style={{ marginTop: 14 }}>
              <button type="button" className="btn primary" onClick={() => act(() => api.post('/sync/mock/anomaly', anomaly), 'Spike injected. Alerts re-evaluated.')}><Icon name="zap" size={16} /> Inject spike</button>
              <button type="button" className="btn" onClick={() => act(() => api.del('/sync/mock/anomaly'), 'Simulated spikes cleared')}>Clear spikes</button>
            </div>
            {status.data?.mock_anomalies?.length ? <p className="tiny" style={{ marginTop: 10 }}>Active: {status.data.mock_anomalies.map((a) => `${PROVIDER_LABEL[a.provider]} ${a.date} ×${a.factor}`).join(', ')}</p> : null}
          </Card>
        )}
      </div>

      <Card title="Sync history" subtitle="Each row is one fetch from one provider">
        {!runs.data ? <Skeleton height={200} /> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Started</th><th>Provider</th><th>Job</th><th>Source</th><th>Status</th><th className="r">Cost rows</th><th className="r">Resources</th><th className="r">Samples</th><th className="r">API calls</th><th>Trigger</th></tr></thead>
              <tbody>
                {runs.data.map((r) => (
                  <tr key={r.id} title={r.error || ''}>
                    <td className="tiny">{dateTime(r.started_at)}</td>
                    <td>{PROVIDER_LABEL[r.provider]}</td>
                    <td>{r.job}</td>
                    <td>{r.data_source}</td>
                    <td><Badge kind={r.status}>{r.status}</Badge></td>
                    <td className="r mono">{r.cost_records}</td>
                    <td className="r mono">{r.resources}</td>
                    <td className="r mono">{r.metric_samples}</td>
                    <td className="r mono">{r.api_calls}</td>
                    <td>{r.triggered_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Toast message={toast} onDone={() => setToast('')} />
    </>
  );
}
