// Page title, subtitle and the page's own action buttons.
export default function PageHeader({ title, subtitle, children }) {
  return (
    <header className="page-head">
      <div style={{ minWidth: 0 }}>
        <h1>{title}</h1>
        {subtitle && <p className="sub">{subtitle}</p>}
      </div>
      {children && <div className="toolbar">{children}</div>}
    </header>
  );
}
