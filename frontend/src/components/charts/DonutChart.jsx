import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { usePrefs } from '../../context/PrefsContext';
import { PROVIDER_COLOR, PROVIDER_LABEL, SERIES_COLORS } from '../../utils/constants';
import ChartTooltip from './ChartTooltip';

export default function DonutChart({ rows = [], centerLabel = 'TOTAL', size = 190 }) {
  const { fmtCompact } = usePrefs();
  const total = rows.reduce((a, r) => a + r.cost, 0);
  const data = rows.map((r, i) => ({ name: PROVIDER_LABEL[r.key] || r.key, value: r.cost, fill: PROVIDER_COLOR[r.key] || SERIES_COLORS[i % SERIES_COLORS.length] }));
  return (
    <div style={{ position: 'relative', width: '100%', height: size }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="68%" outerRadius="92%" paddingAngle={rows.length > 1 ? 2 : 0} stroke="none" isAnimationActive={false}>
            {data.map((d) => (
              <Cell key={d.name} fill={d.fill} />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
        <span className="label" style={{ fontSize: 10 }}>{centerLabel}</span>
        <span className="mono" style={{ fontSize: 18, fontWeight: 600 }}>{fmtCompact(total)}</span>
      </div>
    </div>
  );
}
