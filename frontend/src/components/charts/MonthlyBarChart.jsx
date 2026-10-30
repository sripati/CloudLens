import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { usePrefs } from '../../context/PrefsContext';
import { PROVIDER_COLOR, PROVIDER_LABEL, SERIES_COLORS } from '../../utils/constants';
import ChartTooltip from './ChartTooltip';

// Stacked monthly bars by provider (or any group key).
export default function MonthlyBarChart({ months = [], keys = [], height = 280 }) {
  const { fmtCompact } = usePrefs();
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <BarChart data={months} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
          <YAxis tickFormatter={fmtCompact} tickLine={false} axisLine={false} width={64} />
          <Tooltip content={<ChartTooltip names={PROVIDER_LABEL} />} cursor={{ fill: 'var(--surface-2)' }} />
          {keys.map((k, i) => (
            <Bar key={k} dataKey={k} stackId="m" fill={PROVIDER_COLOR[k] || SERIES_COLORS[i % SERIES_COLORS.length]} name={PROVIDER_LABEL[k] || k} isAnimationActive={false}
              radius={i === keys.length - 1 ? [6, 6, 0, 0] : [0, 0, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
