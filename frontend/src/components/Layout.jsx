import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { usePrefs } from '../context/PrefsContext';
import { useApi } from '../hooks/useApi';
import Icon from './Icon';
import { Badge } from './ui';
import { PROVIDER_LABEL } from '../utils/constants';
import { useEffect } from 'react';

const NAV = [
  { to: '/', label: 'Dashboard', icon: 'dashboard', end: true },
  { to: '/costs', label: 'Cost Explorer', icon: 'cost' },
  { to: '/resources', label: 'Resources', icon: 'resources' },
  { to: '/alerts', label: 'Alerts', icon: 'alerts', badge: true },
  { to: '/reports', label: 'Reports', icon: 'reports' },
  { to: '/accounts', label: 'Cloud Accounts', icon: 'cloud', admin: true },
  { to: '/users', label: 'Users & Roles', icon: 'users', admin: true },
  { to: '/settings', label: 'Settings', icon: 'settings' },
];

export default function Layout() {
  const { isAdmin } = useAuth();
  const { refreshSettings } = usePrefs();
  const { data: status } = useApi('/sync/status', null, { refreshMs: 60000 });
  const { data: rules } = useApi('/alerts/rules', null, { refreshMs: 60000 });
  const firing = (rules || []).filter((r) => r.enabled && r.state === 'firing').length;

  useEffect(() => {
    refreshSettings();
  }, [refreshSettings]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M7 18a5 5 0 1 1 1-9.9A6 6 0 0 1 19 10a4 4 0 0 1-1 8z" />
            <path d="M9 14l2-2 2 2 3-3" />
          </svg>
          <span>
            <span className="brand-name">CloudLens</span>
            <br />
            <span className="tiny">DevOps cost &amp; resource monitor</span>
          </span>
        </a>
        <nav className="nav" aria-label="Main">
          {NAV.filter((n) => isAdmin || !n.admin).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}>
              <Icon name={n.icon} />
              <span>{n.label}</span>
              {n.badge && firing > 0 && <span className="count" aria-label={`${firing} firing alerts`}>{firing}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="side-box">
          <div className="label">Cloud connections</div>
          {(status?.providers || []).map((p) => {
            const st = p.last_run?.status;
            const ok = p.enabled && (st === 'success' || (!st && p.configured));
            return (
              <div className="row" key={p.provider}>
                <span className="dot" style={{ borderRadius: 999, width: 8, height: 8, background: ok ? 'var(--ok)' : st === 'failed' ? 'var(--crit)' : 'var(--warn)' }} />
                <span>{PROVIDER_LABEL[p.provider]}</span>
                <span style={{ marginLeft: 'auto' }}>
                  <Badge kind={status.data_source === 'mock' ? 'info' : ok ? 'ok' : 'warning'}>{status.data_source === 'mock' ? 'Mock' : p.configured ? 'Live' : 'Not set'}</Badge>
                </span>
              </div>
            );
          })}
          {status && <div className="tiny mono" style={{ marginTop: 14 }}>DATA_SOURCE={status.data_source}</div>}
        </div>
      </aside>
      <main id="main" className="main">
        <Outlet />
      </main>
    </div>
  );
}
