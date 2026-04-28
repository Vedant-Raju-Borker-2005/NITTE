import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'rgba(13,21,37,0.95)',
      border: '1px solid rgba(0,170,255,0.3)',
      borderRadius: 8,
      padding: '8px 12px',
      fontSize: 11,
      fontFamily: 'JetBrains Mono, monospace',
      color: '#e8f0fe'
    }}>
      <div style={{ color: '#8899bb', marginBottom: 4 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name}: {Number(p.value).toFixed(1)} kg/hr
        </div>
      ))}
    </div>
  )
}

export function EmissionAreaChart({ data = [], height = 180 }) {
  const formatted = data.map(d => ({
    ...d,
    date: d.timestamp ? d.timestamp.slice(0, 10) : '',
  }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={formatted} margin={{ top: 5, right: 8, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="emissionGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#00ff88" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#00ff88" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="uncertainGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#00aaff" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#00aaff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(68,85,119,0.2)" strokeDasharray="3 3" />
        <XAxis
          dataKey="date"
          tick={{ fill: '#8899bb', fontSize: 10, fontFamily: 'JetBrains Mono' }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: '#8899bb', fontSize: 10, fontFamily: 'JetBrains Mono' }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={100} stroke="rgba(255,179,0,0.5)" strokeDasharray="4 4"
          label={{ value: 'Super-emitter', fill: '#ffb300', fontSize: 9, position: 'insideTopRight' }} />
        <Area
          type="monotone"
          dataKey="emission_rate_kg_hr"
          name="Emission Rate"
          stroke="#00ff88"
          strokeWidth={2}
          fill="url(#emissionGrad)"
          dot={false}
          activeDot={{ r: 4, fill: '#00ff88', strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function GlobalTrendChart({ data = [], height = 140 }) {
  const formatted = data.map(d => ({
    ...d,
    date: d.timestamp ? d.timestamp.slice(5, 10) : '',  // MM-DD
  }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={formatted} margin={{ top: 5, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid stroke="rgba(68,85,119,0.2)" strokeDasharray="3 3" />
        <XAxis
          dataKey="date"
          tick={{ fill: '#8899bb', fontSize: 9, fontFamily: 'JetBrains Mono' }}
          tickLine={false} axisLine={false}
          interval={Math.floor(data.length / 5)}
        />
        <YAxis
          tick={{ fill: '#8899bb', fontSize: 9, fontFamily: 'JetBrains Mono' }}
          tickLine={false} axisLine={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Line
          type="monotone"
          dataKey="total_emission_kg_hr"
          name="Global Total"
          stroke="#00aaff"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: '#00aaff', strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
