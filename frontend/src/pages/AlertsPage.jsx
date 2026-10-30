import { useState } from 'react';
import { api } from '../api/client';
import Icon from '../components/Icon';
import PageHeader from '../components/PageHeader';
import { Badge, Card, Empty, ErrorBox, Modal, Segmented, Skeleton, Toast } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { usePrefs } from '../context/PrefsContext';
import { useApi } from '../hooks/useApi';
import { ENVIRONMENTS, ENV_LABEL, PROVIDERS, PROVIDER_LABEL, RESOURCE_TYPES, TYPE_LABEL } from '../utils/constants';
import { dateTime, timeAgo } from '../utils/format';

const EMPTY_RULE = { name: '', description: '', metric: 'daily_cost', provider: '', environment: '', resource_type: '', operator: '>', threshold: 1000, severity: 'warning', channels: 'default', enabled: true };
const CHANNEL_LABEL = { default: 'Default', slack: 'Slack', teams: 'Teams', both: 'Slack + Teams' };

function RuleForm({ initial, metrics, onClose, onSaved }) {
  const [form, setForm] = useState({ ...EMPTY_RULE, ...initial });
  const [err, setErr] = useState(null);
  const [saving, setSaving] = useState(false);
  const metric = metrics.find((m) => m.key === form.metric);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      const body = { ...form, threshold: Number(form.threshold) };
      if (initial?.id) await api.put(`/alerts/rules/${initial.id}`, body);
      else await api.post('/alerts/rules', body);
      onSaved(initial?.id ? 'Rule updated' : 'Rule created');
    } catch (e) {
      setErr(e);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={initial?.id ? 'Edit alert rule' : 'New alert rule'} onClose={onClose}
      actions={<>
        <button type="button" className="btn" onClick={onClose}>Cancel</button>
        <button type="button" className="btn primary" onClick={save} disabled={saving || form.name.length < 3}>{saving ? 'Saving…' : 'Save rule'}</button>
      </>}>
      <ErrorBox error={err} />
      <div className="form-grid" style={{ marginTop: err ? 12 : 0 }}>
        <div className="field" style={{ gridColumn: '1 / -1' }}>
          <label className="label" htmlFor="r-name">Name</label>
          <input id="r-name" className="input" value={form.name} onChange={set('name')} placeholder="e.g. Production daily spend above $2,000" />
        </div>
        <div className="field" style={{ gridColumn: '1 / -1' }}>
          <label className="label" htmlFor="r-metric">Watch</label>
          <select id="r-metric" className="select" value={form.metric} onChange={set('metric')}>
            {metrics.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="r-op">Condition</label>
          <select id="r-op" className="select" value={form.operator} onChange={set('operator')}>
            {['>', '>=', '<', '<='].map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="r-th">Threshold ({metric?.unit || ''})</label>
          <input id="r-th" type="number" className="input" value={form.threshold} onChange={set('threshold')} step="any" />
        </div>
        <div className="field">
          <label className="label" htmlFor="r-prov">Provider</label>
          <select id="r-prov" className="select" value={form.provider || ''} onChange={set('provider')}>
            <option value="">All providers</option>
            {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="r-env">Environment</label>
          <select id="r-env" className="select" value={form.environment || ''} onChange={set('environment')}>
            <option value="">All environments</option>
            {ENVIRONMENTS.map((e) => <option key={e.value} value={e.value}>{e.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="r-type">Resource type</label>
          <select id="r-type" className="select" value={form.resource_type || ''} onChange={set('resource_type')}>
            <option value="">All types</option>
            {RESOURCE_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="r-sev">Severity</label>
          <select id="r-sev" className="select" value={form.severity} onChange={set('severity')}>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="r-ch">Notify</label>
          <select id="r-ch" className="select" value={form.channels} onChange={set('channels')}>
            <option value="default">Default channel (Settings)</option>
            <option value="slack">Slack</option>
            <option value="teams">Microsoft Teams</option>
            <option value="both">Slack + Teams</option>
          </select>
        </div>
        <div className="field" style={{ gridColumn: '1 / -1' }}>
          <label className="label" htmlFor="r-desc">Description</label>
          <textarea id="r-desc" className="input" value={form.description} onChange={set('description')} />
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 10, minHeight: 44 }}>
          <input type="checkbox" checked={form.enabled} onChange={set('enabled')} style={{ width: 18, height: 18 }} /> Enabled
        </label>
      </div>
    </Modal>
  );
}

function scopeText(r) {
  return [r.provider ? PROVIDER_LABEL[r.provider] : 'All providers', r.environment ? ENV_LABEL[r.environment] : null, r.resource_type ? TYPE_LABEL[r.resource_type] : null].filter(Boolean).join(' · ');
}

export default function AlertsPage() {
  const { isAdmin } = useAuth();
  const { fmt, settings } = usePrefs();
  const [tab, setTab] = useState('rules');
  const [editing, setEditing] = useState(null);
  const [toast, setToast] = useState('');
  const [testChannel, setTestChannel] = useState('default');
  const [sevFilter, setSevFilter] = useState('');
  const rules = useApi('/alerts/rules', null, { refreshMs: 30000 });
  const events = useApi('/alerts/events', { limit: 200, severity: sevFilter }, { refreshMs: 30000 });
  const metrics = useApi('/alerts/metrics');
  const units = Object.fromEntries((metrics.data || []).map((m) => [m.key, m.unit]));
  const fmtVal = (metric, v) => (v === null || v === undefined ? '–' : units[metric] === 'USD' ? fmt(v) : units[metric] === '%' ? `${Number(v).toFixed(1)}%` : Number(v).toFixed(0));

  async function act(fn, msg) {
    try {
      await fn();
      setToast(msg);
      rules.reload();
      events.reload();
    } catch (e) {
      setToast(e.message);
    }
  }

  const firing = (rules.data || []).filter((r) => r.enabled && r.state === 'firing');

  return (
    <>
      <PageHeader title="Alerts" subtitle="Custom cost and utilization thresholds, delivered through Prometheus Alertmanager to Slack and Microsoft Teams">
        {isAdmin && (
          <>
            <button type="button" className="btn" onClick={() => act(() => api.post('/alerts/evaluate'), 'Rules evaluated')}><Icon name="zap" size={16} /> Evaluate now</button>
            <button type="button" className="btn primary" onClick={() => setEditing({})}><Icon name="plus" size={16} strokeWidth={2} /> New rule</button>
          </>
        )}
      </PageHeader>

      <section className="grid-kpi">
        <div className="card"><div className="label">Firing now</div><div className="num" style={{ color: firing.length ? 'var(--crit)' : 'var(--ok)' }}>{firing.length}</div><div className="tiny">of {(rules.data || []).filter((r) => r.enabled).length} enabled rules</div></div>
        <div className="card"><div className="label">Events · 24h</div><div className="num">{(events.data || []).filter((e) => Date.now() - new Date(e.created_at) < 864e5).length}</div><div className="tiny">firing + resolved notifications</div></div>
        <div className="card"><div className="label">Delivery path</div><div style={{ margin: '12px 0', fontWeight: 600 }}>{settings?.system?.alert_delivery === 'direct' ? 'Backend → webhook (direct)' : 'Prometheus → Alertmanager → backend'}</div><div className="tiny">Default channel: {CHANNEL_LABEL[settings?.notification_channel] || '–'}</div></div>
        {isAdmin && (
          <div className="card">
            <div className="label">Test notification</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
              <label className="sr-only" htmlFor="t-ch">Channel</label>
              <select id="t-ch" className="select" style={{ minWidth: 120, flex: 1 }} value={testChannel} onChange={(e) => setTestChannel(e.target.value)}>
                <option value="default">Default</option>
                <option value="slack">Slack</option>
                <option value="teams">Teams</option>
                <option value="both">Both</option>
              </select>
              <button type="button" className="btn" onClick={() => act(() => api.post('/alerts/test', { channel: testChannel }), 'Test notification sent')}><Icon name="send" size={16} /> Send</button>
            </div>
            <div className="tiny" style={{ marginTop: 8 }}>{settings?.system?.slack_is_mock ? 'Webhooks point to the mock receiver' : 'Using configured webhooks'}</div>
          </div>
        )}
      </section>

      <Segmented label="View" value={tab} onChange={setTab} options={[{ value: 'rules', label: `Rules (${rules.data?.length ?? 0})` }, { value: 'events', label: 'Event history' }]} />
      <ErrorBox error={rules.error || events.error} onRetry={rules.reload} />

      {tab === 'rules' ? (
        <Card title="Alert rules" subtitle="Evaluated every minute; state is exported to Prometheus as cloudlens_alert_rule_breached">
          {!rules.data ? <Skeleton height={240} /> : rules.data.length === 0 ? <Empty>No rules yet.</Empty> : (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>State</th><th>Rule</th><th>Scope</th><th>Condition</th><th className="r">Current value</th><th>Severity</th><th>Notify</th><th>Evaluated</th>{isAdmin && <th><span className="sr-only">Actions</span></th>}</tr></thead>
                <tbody>
                  {rules.data.map((r) => (
                    <tr key={r.id} style={{ opacity: r.enabled ? 1 : 0.55 }}>
                      <td><Badge kind={!r.enabled ? 'neutral' : r.state === 'firing' ? 'firing' : 'ok'}>{!r.enabled ? 'Disabled' : r.state === 'firing' ? 'Firing' : 'OK'}</Badge></td>
                      <td style={{ whiteSpace: 'normal', minWidth: 220 }}><strong>{r.name}</strong><div className="tiny">{r.last_detail}</div></td>
                      <td>{scopeText(r)}</td>
                      <td className="mono">{r.operator} {fmtVal(r.metric, r.threshold)}</td>
                      <td className="r mono" style={{ fontWeight: 600 }}>{fmtVal(r.metric, r.last_value)}</td>
                      <td><Badge kind={r.severity}>{r.severity}</Badge></td>
                      <td>{CHANNEL_LABEL[r.channels]}</td>
                      <td className="tiny">{timeAgo(r.last_evaluated_at)}</td>
                      {isAdmin && (
                        <td>
                          <span style={{ display: 'inline-flex', gap: 6 }}>
                            <button type="button" className="btn small" onClick={() => act(() => api.put(`/alerts/rules/${r.id}`, { ...r, enabled: !r.enabled }), r.enabled ? 'Rule disabled' : 'Rule enabled')}>{r.enabled ? 'Disable' : 'Enable'}</button>
                            <button type="button" className="btn small" aria-label={`Edit ${r.name}`} onClick={() => setEditing(r)}><Icon name="edit" size={15} /></button>
                            <button type="button" className="btn small danger" aria-label={`Delete ${r.name}`} onClick={() => window.confirm(`Delete rule "${r.name}"?`) && act(() => api.del(`/alerts/rules/${r.id}`), 'Rule deleted')}><Icon name="trash" size={15} /></button>
                          </span>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : (
        <Card title="Event history" subtitle="Every notification sent, with delivery status"
          actions={<Segmented label="Severity" value={sevFilter} onChange={setSevFilter} options={[{ value: '', label: 'All' }, { value: 'critical', label: 'Critical' }, { value: 'warning', label: 'Warning' }, { value: 'info', label: 'Info' }]} />}>
          {!events.data ? <Skeleton height={240} /> : events.data.length === 0 ? <Empty>No alert events yet.</Empty> : (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Time</th><th>Status</th><th>Severity</th><th>Alert</th><th>Source</th><th>Channels</th><th>Delivery</th><th><span className="sr-only">Acknowledge</span></th></tr></thead>
                <tbody>
                  {events.data.map((e) => (
                    <tr key={e.id}>
                      <td className="tiny">{dateTime(e.created_at)}</td>
                      <td><Badge kind={e.status}>{e.status}</Badge></td>
                      <td><Badge kind={e.severity}>{e.severity}</Badge></td>
                      <td style={{ whiteSpace: 'normal', minWidth: 260 }}><strong>{e.title}</strong><div className="tiny">{e.message}</div></td>
                      <td>{e.source}</td>
                      <td>{e.notified_channels || '–'}</td>
                      <td><Badge kind={e.notification_status}>{e.notification_status}</Badge>{e.notification_error && <div className="tiny" style={{ maxWidth: 220, whiteSpace: 'normal' }}>{e.notification_error}</div>}</td>
                      <td>{e.acknowledged ? <span className="tiny">Acknowledged</span> : <button type="button" className="btn small" onClick={() => act(() => api.post(`/alerts/events/${e.id}/ack`), 'Acknowledged')}><Icon name="check" size={15} /> Ack</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
      {editing && metrics.data && (
        <RuleForm initial={editing} metrics={metrics.data} onClose={() => setEditing(null)} onSaved={(m) => { setEditing(null); setToast(m); rules.reload(); }} />
      )}
      <Toast message={toast} onDone={() => setToast('')} />
    </>
  );
}
