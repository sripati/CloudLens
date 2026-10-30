import { Area, CartesianGrid, ComposedChart, Line, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { usePrefs } from '../../context/PrefsContext';
import { PROVIDER_COLOR, PROVIDER_LABEL, SERIES_COLORS } from '../../utils/constants';
import { shortDate } from '../../utils/format';
import ChartTooltip from './ChartTooltip';

/**
 * Daily cost trend: one line per series key, the total line with an area, a dashed daily-budget
 * reference line and anomaly markers.
 */
export default function CostTrendChart({ data, keys = [], showTotal = true, dailyBudget, anomalies = [], height = 280, showMA = false }) {
  const { fmtCompact } = usePrefs();
  const color = (k, i) => PROVIDER_COLOR[k] || SERIES_COLORS[i % SERIES_COLORS.length];
  const names = { total: 'Total', ma7: '7-day avg', ...PROVIDER_LABEL };
  const byDate = Object.fromEntries((data || []).map((p) => [p.date, p]));
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="totalFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.18} />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} strokeDasharray="0" />
          <XAxis dataKey="date" tickFormatter={shortDate} tickLine={false} axisLine={{ stroke: 'var(--border)' }} minTickGap={28} />
          <YAxis tickFormatter={fmtCompact} tickLine={false} axisLine={false} width={64} />
          <Tooltip content={<ChartTooltip labelFormatter={shortDate} names={names} />} />
          {showTotal && <Area type="monotone" dataKey="total" stroke="var(--text)" strokeWidth={2.5} fill="url(#totalFill)" dot={false} name="Total" isAnimationActive={false} />}
          {keys.map((k, i) => (
            <Line key={k} type="monotone" dataKey={k} stroke={color(k, i)} strokeWidth={2} dot={false} name={names[k] || k} isAnimationActive={false} />
          ))}
          {showMA && <Line type="monotone" dataKey="ma7" stroke="var(--muted)" strokeDasharray="4 4" strokeWidth={1.5} dot={false} name="7-day avg" isAnimationActive={false} />}
          {dailyBudget ? <ReferenceLine y={dailyBudget} stroke="var(--crit)" strokeDasharray="6 5" strokeWidth={1.5} ifOverflow="extendDomain" /> : null}
          {anomalies
            .filter((a) => byDate[a.date])
            .map((a) => (
              <ReferenceDot
                key={`${a.date}-${a.provider}`}
                x={a.date}
                y={keys.includes(a.provider) ? byDate[a.date][a.provider] : byDate[a.date].total}
                r={6}
                fill="var(--surface)"
                stroke="var(--crit)"
                strokeWidth={2}
              />
            ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TrendLegend({ keys, showTotal = true, dailyBudget, anomalies, showMA }) {
  return (
    <div className="legend" aria-hidden="true">
      {showTotal && (
        <span>
          <i className="swatch" style={{ background: 'var(--text)' }} /> Total
        </span>
      )}
      {keys.map((k, i) => (
        <span key={k}>
          <i className="swatch" style={{ background: PROVIDER_COLOR[k] || SERIES_COLORS[i % SERIES_COLORS.length] }} /> {PROVIDER_LABEL[k] || k}
        </span>
      ))}
      {showMA && (
        <span>
          <i className="swatch" style={{ borderTop: '2px dashed var(--muted)', height: 0 }} /> 7-day avg
        </span>
      )}
      {dailyBudget ? (
        <span>
          <i className="swatch" style={{ borderTop: '2px dashed var(--crit)', height: 0 }} /> Daily budget
        </span>
      ) : null}
      {anomalies?.length ? (
        <span>
          <i style={{ width: 10, height: 10, borderRadius: 99, border: '2px solid var(--crit)', display: 'inline-block' }} /> Anomaly
        </span>
      ) : null}
    </div>
  );
}
