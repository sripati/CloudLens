// Dashboard widgets shared by several screens.
import { useNavigate } from 'react-router-dom';
import { usePrefs } from '../context/PrefsContext';
import { ENV_LABEL, PROVIDER_COLOR, PROVIDER_LABEL, TYPE_LABEL } from '../utils/constants';
import { pct, timeAgo } from '../utils/format';
import { Badge, Empty, Progress, ProviderDot, Skeleton, StatusBadge } from './ui';

export function KpiCard({ label, value, sub, subColor = 'var(--muted)', bar, barColor, loading }) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      {loading ? (
        <div style={{ margin: '12px 0' }}>
          <Skeleton height={30} width="70%" />
        </div>
      ) : (
        <div className="num">{value}</div>
      )}
      {bar !== undefined && (
        <div style={{ marginBottom: 10 }}>
          <Progress value={bar} color={barColor} />
        </div>
      )}
      <div style={{ fontSize: 13, fontWeight: 500, color: subColor }}>{sub}</div>
    </div>
  );
}

export function BarList({ rows = [], labels = TYPE_LABEL, highlight, colorFor }) {
  const { fmtCompact } = usePrefs();
  const max = Math.max(...rows.map((r) => r.cost), 1);
  if (!rows.length) return <Empty>No cost data for this selection.</Empty>;
  return (
    <div className="stack" style={{ gap: 14 }}>
      {rows.map((r) => {
        const on = !highlight || highlight === 'all' || highlight === r.key;
        return (
          <div key={r.key}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
              <span>{labels[r.key] || r.key}</span>
              <span className="mono">
                {fmtCompact(r.cost)} <span className="muted">· {pct(r.pct, 0)}</span>
              </span>
            </div>
            <Progress value={(r.cost / max) * 100} color={colorFor ? colorFor(r.key) : on ? 'var(--accent)' : 'var(--faint)'} />
          </div>
        );
      })}
    </div>
  );
}

export function ProviderLegendRows({ rows = [] }) {
  const { fmt } = usePrefs();
  return (
    <div className="stack" style={{ gap: 10 }}>
      {rows.map((r) => (
        <div key={r.key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ProviderDot color={PROVIDER_COLOR[r.key]} />
          <span style={{ fontWeight: 600, flex: 1 }}>{PROVIDER_LABEL[r.key] || r.key}</span>
          <span className="muted">{pct(r.pct)}</span>
          <span className="mono">{fmt(r.cost)}</span>
        </div>
      ))}
    </div>
  );
}

function UtilRow({ label, value, color }) {
  const over = value !== null && value !== undefined && value >= 80;
  return (
    <>
      <span className="muted">{label}</span>
      <Progress value={value ?? 0} color={over ? 'var(--crit)' : color} tick={80} />
      <span className="mono" style={{ textAlign: 'right' }}>{value === null || value === undefined ? '–' : `${Math.round(value)}%`}</span>
    </>
  );
}

export function UtilizationPanel({ providers = [] }) {
  if (!providers.length) return <Empty>No utilization samples yet.</Empty>;
  return (
    <div className="stack" style={{ gap: 18 }}>
      {providers.map((p) => (
        <div key={p.provider}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <ProviderDot color={PROVIDER_COLOR[p.provider]} />
            <span style={{ fontWeight: 600, flex: 1 }}>{PROVIDER_LABEL[p.provider]}</span>
            <span className="tiny">7-day avg CPU {pct(p.cpu_avg, 0)} · peak {pct(p.cpu_peak, 0)}</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '64px minmax(0,1fr) 44px', gap: 8, alignItems: 'center' }}>
            <UtilRow label="CPU" value={p.cpu_now} color={PROVIDER_COLOR[p.provider]} />
            <UtilRow label="Memory" value={p.mem_now} color={PROVIDER_COLOR[p.provider]} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function UtilBar({ value }) {
  if (value === null || value === undefined) return <span className="muted">–</span>;
  const color = value >= 80 ? 'var(--crit)' : value < 10 ? 'var(--warn)' : 'var(--ok)';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <span className="track" style={{ width: 72, height: 6, display: 'inline-block' }}>
        <span style={{ width: `${Math.min(100, value)}%`, background: color }} />
      </span>
      <span className="mono">{Math.round(value)}%</span>
    </span>
  );
}

export function ResourceTable({ rows = [], loading, compact: small = false }) {
  const { fmt } = usePrefs();
  const navigate = useNavigate();
  if (loading && !rows.length) return <Skeleton height={220} />;
  if (!rows.length) return <Empty>No resources match these filters.</Empty>;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th scope="col">Resource</th>
            <th scope="col">Provider</th>
            <th scope="col">Type</th>
            <th scope="col">Environment</th>
            {!small && <th scope="col">SKU</th>}
            <th scope="col">Region</th>
            <th scope="col">Utilization</th>
            <th scope="col" className="r">Cost</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="clickable" onClick={() => navigate(`/resources/${r.id}`)}>
              <td className="mono" style={{ fontWeight: 600 }}>
                <a href={`/resources/${r.id}`} onClick={(e) => { e.preventDefault(); navigate(`/resources/${r.id}`); }} style={{ color: 'var(--text)', textDecoration: 'none' }}>
                  {r.name}
                </a>
              </td>
              <td>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <ProviderDot color={PROVIDER_COLOR[r.provider]} size={8} />
                  {PROVIDER_LABEL[r.provider]}
                </span>
              </td>
              <td>{TYPE_LABEL[r.resource_type] || r.resource_type}</td>
              <td>{ENV_LABEL[r.environment] || r.environment}</td>
              {!small && <td className="mono muted">{r.sku || '–'}</td>}
              <td className="mono muted">{r.region}</td>
              <td>{r.resource_type === 'storage' ? <UtilBar value={r.storage} /> : <UtilBar value={r.cpu} />}</td>
              <td className="r mono" style={{ fontWeight: 600 }}>{fmt(r.cost)}</td>
              <td><StatusBadge status={r.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AlertList({ events = [], empty = 'No alerts yet.' }) {
  if (!events.length) return <Empty>{empty}</Empty>;
  return (
    <div className="stack">
      {events.map((e) => (
        <div className="alert-item" key={e.id}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <span style={{ display: 'inline-flex', gap: 6 }}>
              <Badge kind={e.status === 'resolved' ? 'resolved' : e.severity}>{e.status === 'resolved' ? 'Resolved' : e.severity[0].toUpperCase() + e.severity.slice(1)}</Badge>
            </span>
            <span className="tiny">{timeAgo(e.created_at)}</span>
          </div>
          <div className="t">{e.title}</div>
          <div className="tiny" style={{ fontSize: 13 }}>
            {e.message.length > 140 ? `${e.message.slice(0, 140)}…` : e.message}
          </div>
          <div className="tiny" style={{ marginTop: 6 }}>
            {e.notified_channels ? `Sent to ${e.notified_channels.replace(',', ' + ')}` : 'Not sent'} · <span style={{ color: e.notification_status === 'sent' ? 'var(--ok)' : 'var(--warn)' }}>{e.notification_status}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
