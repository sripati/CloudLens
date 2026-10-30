import { useAuth } from '../context/AuthContext';
import { usePrefs } from '../context/PrefsContext';
import Icon from './Icon';
import { Segmented } from './ui';

// Page title + global controls (currency, theme, user menu) shown at the top of every screen.
export default function PageHeader({ title, subtitle, children }) {
  const { user, logout, isAdmin } = useAuth();
  const { currency, setCurrency, theme, toggleTheme } = usePrefs();
  const initials = (user?.full_name || user?.email || '?')
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0].toUpperCase())
    .join('');
  return (
    <header className="page-head">
      <div style={{ minWidth: 0 }}>
        <h1>{title}</h1>
        {subtitle && <p className="sub">{subtitle}</p>}
      </div>
      <div className="toolbar">
        {children}
        <Segmented
          label="Currency"
          value={currency}
          onChange={setCurrency}
          options={[
            { value: 'USD', label: 'USD $' },
            { value: 'INR', label: 'INR ₹' },
          ]}
        />
        <button type="button" className="btn" onClick={toggleTheme}>
          <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16} />
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
        <div className="user-chip">
          <span className="avatar" aria-hidden="true">{initials}</span>
          <span style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontWeight: 600 }}>{user?.full_name || user?.email}</span>
            <span className="tiny">{isAdmin ? 'Admin · full access' : 'Viewer · read-only'}</span>
          </span>
          <button type="button" className="btn small" onClick={logout} aria-label="Sign out" title="Sign out">
            <Icon name="logout" size={16} />
          </button>
        </div>
      </div>
    </header>
  );
}
