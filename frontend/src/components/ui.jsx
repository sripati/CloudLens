// Small reusable UI primitives.
import { useEffect } from 'react';
import { STATUS_LABEL } from '../utils/constants';

export function Card({ title, subtitle, actions, children, className = '', ...rest }) {
  return (
    <section className={`card ${className}`} {...rest}>
      {(title || actions) && (
        <div className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p className="sub">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Segmented({ label, options, value, onChange }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={String(o.value)} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Badge({ kind = 'neutral', children }) {
  return <span className={`badge ${kind}`}>{children}</span>;
}

export function StatusBadge({ status }) {
  return <Badge kind={status}>{STATUS_LABEL[status] || status}</Badge>;
}

export function ProviderDot({ color, size = 10 }) {
  return <span className="dot" style={{ background: color, width: size, height: size }} />;
}

export function Progress({ value, color = 'var(--accent)', tick }) {
  const w = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="track" role="progressbar" aria-valuenow={Math.round(w)} aria-valuemin={0} aria-valuemax={100}>
      <span style={{ width: `${w}%`, background: color }} />
      {tick !== undefined && <span className="tick" style={{ left: `${tick}%` }} />}
    </div>
  );
}

export function Skeleton({ height = 20, width = '100%' }) {
  return <div className="skeleton" style={{ height, width }} aria-hidden="true" />;
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="error-box" role="alert">
      {error.message || String(error)}{' '}
      {onRetry && (
        <button type="button" className="btn link" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>;
}

export function Modal({ title, onClose, children, actions }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <h2 style={{ margin: '0 0 16px', fontSize: 18 }}>{title}</h2>
        {children}
        {actions && <div className="modal-actions">{actions}</div>}
      </div>
    </div>
  );
}

export function Toast({ message, onDone }) {
  useEffect(() => {
    if (!message) return undefined;
    const id = setTimeout(onDone, 4000);
    return () => clearTimeout(id);
  }, [message, onDone]);
  if (!message) return null;
  return (
    <div className="toast" role="status">
      {message}
    </div>
  );
}

export function pctColor(p) {
  if (p === null || p === undefined) return 'var(--muted)';
  if (p >= 100) return 'var(--crit)';
  if (p >= 80) return 'var(--warn)';
  return 'var(--ok)';
}
