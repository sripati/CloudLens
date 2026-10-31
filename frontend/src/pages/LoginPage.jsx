import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={location.state?.from || '/'} replace />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(email.trim(), password);
      navigate(location.state?.from || '/', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={submit} aria-labelledby="login-title">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M7 18a5 5 0 1 1 1-9.9A6 6 0 0 1 19 10a4 4 0 0 1-1 8z" /><path d="M9 14l2-2 2 2 3-3" />
          </svg>
          <div>
            <div className="brand-name">CloudLens</div>
            <div className="tiny">DevOps cost &amp; resource monitor</div>
          </div>
        </div>
        <h1 id="login-title" style={{ fontSize: 22, margin: '0 0 4px' }}>Sign in</h1>
        <p className="sub" style={{ marginBottom: 18 }}>Monitor AWS, Azure and GCP spend in one place.</p>
        {error && <div className="error-box" role="alert" style={{ marginBottom: 14 }}>{error}</div>}
        <div className="stack" style={{ gap: 14 }}>
          <div className="field">
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
          </div>
          <div className="field">
            <label className="label" htmlFor="password">Password</label>
            <input id="password" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </div>
          <button type="submit" className="btn primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </div>
        <p className="tiny" style={{ marginTop: 16 }}>Default accounts are defined in <span className="mono">.env</span> (ADMIN_EMAIL / VIEWER_EMAIL). Change them before deploying.</p>
      </form>
    </div>
  );
}
