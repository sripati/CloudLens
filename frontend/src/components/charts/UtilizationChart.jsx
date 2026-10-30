import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { PROVIDER_COLOR, PROVIDER_LABEL } from '../../utils/constants';
import ChartTooltip from './ChartTooltip';

const fmtTs = (ts) => {
  const d = new Date(ts);
  return `${d.getDate()} ${d.toLocaleString('en', { month: 'short' })} ${String(d.getHours()).padStart(2, '0')}:00`;
};

// CPU % over time, one line per provider (or a single resource), with the 80% threshold.
export default function UtilizationChart({ data = [], keys = [], height = 260, threshold = 80, names = PROVIDER_LABEL, colors = PROVIDER_COLOR }) {
  return (
    <>
    <div className="legend" aria-hidden="true" style={{ marginBottom: 8 }}>
      {keys.map((k) => (
        <span key={k}><i className="swatch" style={{ background: colors[k] || 'var(--accent)' }} /> {names[k] || k}</span>
      ))}
      <span><i className="swatch" style={{ borderTop: '2px dashed var(--crit)', height: 0 }} /> {threshold}% threshold</span>
    </div>
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="ts" tickFormatter={fmtTs} tickLine={false} axisLine={{ stroke: 'var(--border)' }} minTickGap={40} />
          <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tickLine={false} axisLine={false} width={44} />
          <Tooltip content={<ChartTooltip unit="%" labelFormatter={fmtTs} names={names} />} />
          <ReferenceLine y={threshold} stroke="var(--crit)" strokeDasharray="6 5" />
          {keys.map((k) => (
            <Line key={k} type="monotone" dataKey={k} stroke={colors[k] || 'var(--accent)'} strokeWidth={2} dot={false} isAnimationActive={false} name={names[k] || k} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
    </>
  );
}
