import { useState } from 'react';
import { api } from '../api/client';
import CloudConfigModal from '../components/CloudConfigModal';
import Icon from '../components/Icon';
import PageHeader from '../components/PageHeader';
import { Badge, Card, ErrorBox, Skeleton, Toast } from '../components/ui';
import { usePrefs } from '../context/PrefsContext';
import { useApi } from '../hooks/useApi';
import { ENV_LABEL, MODE_LABEL, PROVIDERS, PROVIDER_LABEL } from '../utils/constants';
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
  const [configuring, setConfiguring] = useState(null);
  const { refreshSettings, refreshBounds } = usePrefs();
  const mockProviders = PROVIDERS.filter((p) => (status.data?.providers || []).some((s) => s.provider === p.value && s.mode === 'mock'));
  const spikeProvider = mockProviders.some((p) => p.value === anomaly.provider) ? anomaly.provider : mockProviders[0]?.value;

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

  function refreshAll() {
    status.reload();
    runs.reload();
    refreshSettings();
    refreshBounds();
  }

  function afterConfigChange(message) {
    setToast(message);
    refreshAll();
    setTimeout(refreshAll, 3000);
  }

  async function changeMode(p, mode) {
    if (mode === 'live' && !p.verified) {
      setConfiguring({ provider: p.provider, reason: `Enter the connection details and pass the test to use ${MODE_LABEL.live} data for this cloud.` });
      return;
    }
    try {
      await api.put(`/cloud-accounts/${p.provider}/mode`, { mode });
      afterConfigChange(`${PROVIDER_LABEL[p.provider]} switched to ${MODE_LABEL[mode]}. Loading its data now.`);
    } catch (e) {
      setToast(e.message);
    }
  }

  return (
    <>
      <PageHeader title="Cloud Accounts" subtitle={`Choose ${MODE_LABEL.mock} or ${MODE_LABEL.live} data for each cloud, configure connections, and review sync history`} />
      <ErrorBox error={status.error} onRetry={status.reload} />
      {status.data && (
        <div className="notice">
          Each cloud has its own mode. <strong>{MODE_LABEL.mock}</strong> uses the built-in generator. <strong>{MODE_LABEL.live}</strong> reads a real cloud account for each configured environment; environments without a configuration show no data.
          {status.data.data_source === 'mixed' && <> Dashboard totals currently combine real and simulated cost.</>}
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
                    <dt><label htmlFor={`mode-${p.provider}`}>Mode</label></dt>
                    <dd>
                      <select id={`mode-${p.provider}`} className="select mode-select" value={p.mode} onChange={(e) => changeMode(p, e.target.value)}>
                        {Object.entries(MODE_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    </dd>
                    <dt>Connections</dt>
                    <dd>
                      {p.connections?.length ? (
                        <div className="stack" style={{ gap: 6 }}>
                          {p.connections.map((c) => (
                            <div key={c.environment}>
                              <Badge kind={c.verified ? 'ok' : 'warning'}>{ENV_LABEL[c.environment]} · {c.verified ? 'Validated' : 'Not validated'}</Badge>
                              <div className="tiny mono">{c.account}</div>
                              {c.last_run?.error && <div className="tiny" style={{ color: 'var(--warn)' }}>{c.last_run.error}</div>}
                            </div>
                          ))}
                        </div>
                      ) : <Badge kind="neutral">Not configured</Badge>}
                    </dd>
                    {p.mode === 'mock' && <><dt>Account</dt><dd className="mono">{p.account_id || '–'}</dd></>}
                    <dt>Last run</dt><dd>{p.last_run ? <><Badge kind={p.last_run.status}>{p.last_run.status}</Badge> {timeAgo(p.last_run.started_at)}</> : '–'}</dd>
                    <dt>Last success</dt><dd>{dateTime(p.last_success_at)}</dd>
                    {p.mode === 'mock' && p.last_run?.error && <><dt>Error</dt><dd style={{ color: 'var(--warn)' }}>{p.last_run.error}</dd></>}
                  </dl>
                  {t && <div className={t.ok ? 'notice' : 'error-box'} style={{ marginTop: 12 }}>{t.message}{t.account ? ` · ${t.account}` : ''}</div>}
                  <div className="toolbar" style={{ marginTop: 14 }}>
                    <button type="button" className="btn small" onClick={() => setConfiguring({ provider: p.provider })}><Icon name="settings" size={14} /> Configuration</button>
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
        {mockProviders.length > 0 && (
          <Card className="flex-1" title="Demo: simulate a cost spike" subtitle="Mock mode only · multiplies one day's cost for a provider so the anomaly and budget alerts fire">
            <div className="form-grid">
              <div className="field"><label className="label" htmlFor="a-p">Provider</label>
                <select id="a-p" className="select" value={spikeProvider} onChange={(e) => setAnomaly({ ...anomaly, provider: e.target.value })}>{mockProviders.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}</select></div>
              <div className="field"><label className="label" htmlFor="a-f">Multiplier</label>
                <input id="a-f" type="number" min="1.1" max="10" step="0.1" className="input" value={anomaly.factor} onChange={(e) => setAnomaly({ ...anomaly, factor: Number(e.target.value) })} /></div>
              <div className="field"><label className="label" htmlFor="a-d">Days ago</label>
                <input id="a-d" type="number" min="0" max="30" className="input" value={anomaly.days_ago} onChange={(e) => setAnomaly({ ...anomaly, days_ago: Number(e.target.value) })} /></div>
            </div>
            <div className="toolbar" style={{ marginTop: 14 }}>
              <button type="button" className="btn primary" onClick={() => act(() => api.post('/sync/mock/anomaly', { ...anomaly, provider: spikeProvider }), 'Spike injected. Alerts re-evaluated.')}><Icon name="zap" size={16} /> Inject spike</button>
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
              <thead><tr><th>Started</th><th>Provider</th><th>Environment</th><th>Job</th><th>Source</th><th>Status</th><th className="r">Cost rows</th><th className="r">Resources</th><th className="r">Samples</th><th className="r">API calls</th><th>Trigger</th></tr></thead>
              <tbody>
                {runs.data.map((r) => (
                  <tr key={r.id} title={r.error || ''}>
                    <td className="tiny">{dateTime(r.started_at)}</td>
                    <td>{PROVIDER_LABEL[r.provider]}</td>
                    <td>{ENV_LABEL[r.environment] || 'All'}</td>
                    <td>{r.job}</td>
                    <td>{MODE_LABEL[r.data_source] || r.data_source}</td>
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
      {configuring && <CloudConfigModal provider={configuring.provider} reason={configuring.reason} onClose={() => setConfiguring(null)} onChanged={afterConfigChange} />}
      <Toast message={toast} onDone={() => setToast('')} />
    </>
  );
}
