import { useEffect, useState } from 'react';
import { api } from '../api/client';
import PageHeader from '../components/PageHeader';
import { Card, ErrorBox, Segmented, Skeleton, Toast } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { usePrefs } from '../context/PrefsContext';
import { MODE_LABEL, PROVIDER_LABEL } from '../utils/constants';

export default function SettingsPage() {
  const { isAdmin } = useAuth();
  const { settings, refreshSettings, theme, toggleTheme, currency, setCurrency, fmt } = usePrefs();
  const [form, setForm] = useState(null);
  const [err, setErr] = useState(null);
  const [toast, setToast] = useState('');
  const [pw, setPw] = useState({ current_password: '', new_password: '' });
  const [hooks, setHooks] = useState({ slack: '', teams: '' });

  useEffect(() => {
    if (settings) setForm({ ...settings, provider_budgets_usd: { ...settings.provider_budgets_usd } });
  }, [settings]);

  async function useTestInbox(channel) {
    setErr(null);
    try {
      await api.put('/settings', { [`${channel}_webhook_url`]: '' });
      await refreshSettings();
      setToast('This channel now uses the test inbox.');
    } catch (e) {
      setErr(e);
    }
  }

  function webhookField(channel, label, saved) {
    const id = `s-${channel}-hook`;
    return (
      <div className="field">
        <label className="label" htmlFor={id}>{label}</label>
        <input id={id} type="password" className="input mono" autoComplete="new-password" placeholder={saved ? 'Saved. Leave blank to keep it.' : 'https://...'} value={hooks[channel]} onChange={(e) => setHooks({ ...hooks, [channel]: e.target.value })} />
        <span className="field-help">
          {saved ? 'Using the saved URL. ' : 'Using the bundled test inbox. '}
          {saved && <button type="button" className="btn link" onClick={() => useTestInbox(channel)}>Use test inbox</button>}
        </span>
      </div>
    );
  }

  async function save() {
    setErr(null);
    try {
      await api.put('/settings', {
        monthly_budget_usd: Number(form.monthly_budget_usd),
        provider_budgets_usd: Object.fromEntries(Object.entries(form.provider_budgets_usd).map(([k, v]) => [k, Number(v)])),
        exchange_rate_inr: Number(form.exchange_rate_inr),
        default_currency: form.default_currency,
        notification_channel: form.notification_channel,
        idle_cpu_threshold: Number(form.idle_cpu_threshold),
        underutilized_cpu_threshold: Number(form.underutilized_cpu_threshold),
        ...(hooks.slack.trim() ? { slack_webhook_url: hooks.slack.trim() } : {}),
        ...(hooks.teams.trim() ? { teams_webhook_url: hooks.teams.trim() } : {}),
      });
      setHooks({ slack: '', teams: '' });
      await refreshSettings();
      await api.post('/alerts/evaluate');
      setToast('Settings saved. Alert rules re-evaluated.');
    } catch (e) {
      setErr(e);
    }
  }

  async function changePassword() {
    try {
      await api.post('/auth/change-password', pw);
      setPw({ current_password: '', new_password: '' });
      setToast('Password changed');
    } catch (e) {
      setToast(e.message);
    }
  }

  const ro = !isAdmin;
  const sys = settings?.system;
  return (
    <>
      <PageHeader title="Settings" subtitle={isAdmin ? 'Budgets, currency, notification channels and thresholds' : 'Read-only: only admins can change organisation settings'} />
      <ErrorBox error={err} />
      <div className="row-wrap">
        <Card className="flex-1" title="Display preferences" subtitle="Saved in this browser">
          <div className="stack" style={{ gap: 16 }}>
            <div className="field"><span className="label">Theme</span><Segmented label="Theme" value={theme} onChange={(v) => v !== theme && toggleTheme()} options={[{ value: 'dark', label: 'Dark' }, { value: 'light', label: 'Light' }]} /></div>
            <div className="field"><span className="label">Display currency</span><Segmented label="Display currency" value={currency} onChange={setCurrency} options={[{ value: 'USD', label: 'USD $' }, { value: 'INR', label: 'INR ₹' }]} /></div>
            <p className="tiny">Example: {fmt(1234.5, 2)}</p>
          </div>
        </Card>
        <Card className="flex-2" title="Budgets & currency" subtitle="Budgets drive the budget KPI, forecast and the budget alert rules">
          {!form ? <Skeleton height={200} /> : (
            <fieldset disabled={ro} style={{ border: 0, padding: 0, margin: 0 }}>
              <div className="form-grid">
                <div className="field"><label className="label" htmlFor="s-b">Monthly budget (USD) · all clouds</label><input id="s-b" type="number" className="input" value={form.monthly_budget_usd} onChange={(e) => setForm({ ...form, monthly_budget_usd: e.target.value })} /></div>
                {['aws', 'azure', 'gcp'].map((p) => (
                  <div className="field" key={p}><label className="label" htmlFor={`s-${p}`}>{p.toUpperCase()} budget (USD)</label>
                    <input id={`s-${p}`} type="number" className="input" value={form.provider_budgets_usd[p] ?? ''} onChange={(e) => setForm({ ...form, provider_budgets_usd: { ...form.provider_budgets_usd, [p]: e.target.value } })} /></div>
                ))}
                <div className="field"><label className="label" htmlFor="s-r">Exchange rate (INR per 1 USD)</label><input id="s-r" type="number" step="0.01" className="input" value={form.exchange_rate_inr} onChange={(e) => setForm({ ...form, exchange_rate_inr: e.target.value })} /></div>
                <div className="field"><label className="label" htmlFor="s-dc">Default currency (new users)</label>
                  <select id="s-dc" className="select" value={form.default_currency} onChange={(e) => setForm({ ...form, default_currency: e.target.value })}><option value="USD">USD</option><option value="INR">INR</option></select></div>
              </div>
            </fieldset>
          )}
        </Card>
      </div>
      <div className="row-wrap">
        <Card className="flex-1" title="Notifications" subtitle="Default channel for rules set to “Default”">
          {!form ? <Skeleton height={120} /> : (
            <fieldset disabled={ro} style={{ border: 0, padding: 0, margin: 0 }}>
              <div className="field"><label className="label" htmlFor="s-ch">Preferred channel</label>
                <select id="s-ch" className="select" value={form.notification_channel} onChange={(e) => setForm({ ...form, notification_channel: e.target.value })}>
                  <option value="slack">Slack</option><option value="teams">Microsoft Teams</option><option value="both">Slack + Teams</option>
                </select></div>
              {sys?.webhooks?.unreadable && <div className="error-box" style={{ marginTop: 12 }}>The saved webhook URLs cannot be decrypted because JWT_SECRET changed. Enter them again.</div>}
              {isAdmin && (
                <div className="stack" style={{ marginTop: 12 }}>
                  {webhookField('slack', 'Slack webhook URL', sys?.webhooks?.slack_saved)}
                  {webhookField('teams', 'Microsoft Teams webhook URL', sys?.webhooks?.teams_saved)}
                </div>
              )}
              <p className="tiny" style={{ marginTop: 12 }}>Webhook URLs are secrets: they are stored encrypted and never shown again.</p>
            </fieldset>
          )}
        </Card>
        <Card className="flex-1" title="Optimization thresholds" subtitle="Used by recommendations and the idle-resource alert">
          {!form ? <Skeleton height={120} /> : (
            <fieldset disabled={ro} style={{ border: 0, padding: 0, margin: 0 }}>
              <div className="form-grid">
                <div className="field"><label className="label" htmlFor="s-idle">Idle below CPU %</label><input id="s-idle" type="number" className="input" value={form.idle_cpu_threshold} onChange={(e) => setForm({ ...form, idle_cpu_threshold: e.target.value })} /></div>
                <div className="field"><label className="label" htmlFor="s-under">Under-utilized below CPU %</label><input id="s-under" type="number" className="input" value={form.underutilized_cpu_threshold} onChange={(e) => setForm({ ...form, underutilized_cpu_threshold: e.target.value })} /></div>
              </div>
            </fieldset>
          )}
        </Card>
        <Card className="flex-1" title="System" subtitle="Read-only">
          {!sys ? <Skeleton height={120} /> : (
            <dl className="kv">
              <dt>Data source</dt><dd>{Object.entries(sys.provider_modes || {}).map(([p, m]) => <div key={p}>{PROVIDER_LABEL[p]}: {MODE_LABEL[m]}</div>)}</dd>
              <dt>Providers</dt><dd>{sys.enabled_providers.join(', ')}</dd>
              <dt>Alert delivery</dt><dd>{sys.alert_delivery}</dd>
              <dt>Daily sync</dt><dd>{sys.daily_sync_time} {sys.timezone}</dd>
              <dt>Metrics every</dt><dd>{sys.metrics_interval_minutes} min</dd>
              <dt>Intraday cost</dt><dd>every {sys.intraday_cost_refresh_minutes} min</dd>
              <dt>Retention</dt><dd>{sys.metrics_retention_days} days of samples</dd>
              <dt>Deployment</dt><dd>{sys.app_env}</dd>
            </dl>
          )}
        </Card>
      </div>
      {isAdmin && form && <div><button type="button" className="btn primary" onClick={save}>Save settings</button></div>}
      <Card title="Change password">
        <div className="form-grid" style={{ maxWidth: 640 }}>
          <div className="field"><label className="label" htmlFor="pw-c">Current password</label><input id="pw-c" type="password" className="input" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} autoComplete="current-password" /></div>
          <div className="field"><label className="label" htmlFor="pw-n">New password (min 8)</label><input id="pw-n" type="password" className="input" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} autoComplete="new-password" /></div>
        </div>
        <button type="button" className="btn" style={{ marginTop: 14 }} disabled={!pw.current_password || pw.new_password.length < 8} onClick={changePassword}>Update password</button>
      </Card>
      <Toast message={toast} onDone={() => setToast('')} />
    </>
  );
}
