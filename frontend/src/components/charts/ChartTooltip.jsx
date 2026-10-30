import { usePrefs } from '../../context/PrefsContext';

// Themed Recharts tooltip. `labelFormatter` formats the x value; values are formatted as money
// unless `unit` is given (e.g. '%').
export default function ChartTooltip({ active, payload, label, labelFormatter, unit, names = {} }) {
  const { fmt } = usePrefs();
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{labelFormatter ? labelFormatter(label) : label}</div>
      {payload
        .filter((p) => p.value !== null && p.value !== undefined)
        .map((p) => (
          <div className="tt-row" key={p.dataKey}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span className="dot" style={{ background: p.color || p.stroke || p.fill }} />
              {names[p.dataKey] || p.name || p.dataKey}
            </span>
            <span className="mono">{unit ? `${Number(p.value).toFixed(1)}${unit}` : fmt(p.value)}</span>
          </div>
        ))}
    </div>
  );
}
