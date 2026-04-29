import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Activity, MapPin, Clock, X } from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer, YAxis } from 'recharts'
import { getFacilities, getTopPolluters, getAlerts, getHeatmap, getTimeseries } from '../../api/client.js'

export default function HomeDashboard() {
  const [alertDismissed, setAlertDismissed] = useState(false)

  // React Query hooks for data
  const { data: facilitiesData } = useQuery({
    queryKey: ['facilities'],
    queryFn: () => getFacilities(),
    refetchInterval: 60000,
  })
  const { data: pollutersData } = useQuery({
    queryKey: ['topPolluters'],
    queryFn: () => getTopPolluters(5),
    refetchInterval: 60000,
  })
  const { data: alertsData } = useQuery({ queryKey: ['alerts'], queryFn: () => getAlerts(), refetchInterval: 30000 })
  const { data: heatmapData } = useQuery({
    queryKey: ['heatmap'],
    queryFn: () => getHeatmap(),
    refetchInterval: 60000,
  })

  const facilities = facilitiesData?.facilities || []
  const topPolluters = pollutersData?.top_polluters || []
  const alerts = alertsData?.alerts || []
  const hotspots = heatmapData?.hotspots || []

  const criticalAlerts = alerts.filter(a => a.severity === 'CRITICAL')
  const totalMonitoredRate = facilities.reduce((sum, f) => sum + (f.historical_emission_rate || 0), 0)

  return (
    <div style={{ padding: '24px', height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* Global Alert Banner */}
      {criticalAlerts.length > 0 && !alertDismissed && (
        <div style={{
          background: 'rgba(255, 68, 68, 0.15)',
          border: '1px solid rgba(255, 68, 68, 0.4)',
          borderRadius: '8px',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: '#ff4444'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <AlertTriangle size={20} />
            <span style={{ fontWeight: 600 }}>{criticalAlerts.length} CRITICAL alert(s) active. Immediate review required.</span>
            <Link to="/alerts" style={{ color: '#fff', textDecoration: 'underline', fontSize: '14px', marginLeft: '8px' }}>
              View Alerts
            </Link>
          </div>
          <button 
            onClick={() => setAlertDismissed(true)}
            style={{ background: 'transparent', border: 'none', color: '#ff4444', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>
      )}

      {/* KPI Tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
        <KpiTile 
          icon={<Activity size={20} color="var(--neon-amber)" />}
          label="Total Monitored Rate"
          value={`${totalMonitoredRate.toFixed(1)}`}
          unit="kg/hr"
        />
        <KpiTile 
          icon={<AlertTriangle size={20} color="#ff4444" />}
          label="Active CRITICAL Alerts"
          value={criticalAlerts.length}
          unit="alerts"
        />
        <KpiTile 
          icon={<MapPin size={20} color="var(--neon-blue)" />}
          label="Facilities Online"
          value={facilities.length}
          unit="monitored"
        />
        <KpiTile 
          icon={<Clock size={20} color="var(--neon-green)" />}
          label="Last Scan"
          value="Live"
          unit="updating"
        />
      </div>

      {/* Two Column Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', flex: 1, minHeight: 0 }}>
        
        {/* Left: Top 5 Polluters */}
        <div className="glass" style={{ display: 'flex', flexDirection: 'column', padding: '20px', overflow: 'hidden' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', color: 'var(--text-primary)' }}>Top 5 Polluters</h3>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {topPolluters.map((fac, i) => (
              <div key={fac.id} style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '12px 0', borderBottom: '1px solid var(--border)'
              }}>
                <span style={{
                  width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                  background: i < 3 ? 'rgba(255,68,68,0.15)' : 'rgba(255,140,0,0.1)',
                  border: `1px solid ${i < 3 ? '#ff4444' : '#ff8c00'}40`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 800, color: i < 3 ? '#ff4444' : '#ff8c00'
                }}>{i + 1}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {fac.name}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    {fac.country}
                  </div>
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '14px', fontWeight: 700,
                  color: fac.historical_emission_rate > 800 ? 'var(--neon-red)' : 'var(--neon-amber)',
                  flexShrink: 0 }}>
                  {fac.historical_emission_rate} <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>kg/hr</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Trend Sparklines */}
        <div className="glass" style={{ display: 'flex', flexDirection: 'column', padding: '20px', overflow: 'hidden' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', color: 'var(--text-primary)' }}>7-Day Emission Trends</h3>
          <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {topPolluters.slice(0, 4).map(fac => (
              <FacilitySparkline key={fac.id} facility={fac} />
            ))}
          </div>
        </div>

      </div>

      {/* Bottom emission ticker */}
      <div style={{
        background: 'rgba(8,13,26,0.9)', border: '1px solid var(--border)', borderRadius: '8px',
        padding: '12px 20px', display: 'flex', alignItems: 'center', gap: '24px',
        overflow: 'hidden', flexShrink: 0
      }}>
        <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing:'0.1em', color:'var(--text-muted)', flexShrink:0 }}>
          LIVE EMISSION TICKER
        </span>
        <div style={{ display: 'flex', gap: '24px', overflow: 'hidden' }}>
          {hotspots.slice(0, 8).map((h, i) => (
            <span key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', whiteSpace: 'nowrap' }}>
              <span style={{ color: 'var(--text-secondary)' }}>{h.region}</span>
              <span style={{ color: h.intensity > 0.7 ? 'var(--neon-red)' : 'var(--neon-amber)', marginLeft: '8px' }}>
                {h.emission_rate_kg_hr.toFixed(0)} kg/hr
              </span>
            </span>
          ))}
        </div>
      </div>

    </div>
  )
}

function KpiTile({ icon, label, value, unit }) {
  return (
    <div className="glass" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
        {icon}
        <span style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)' }}>{value}</span>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{unit}</span>
      </div>
    </div>
  )
}

function FacilitySparkline({ facility }) {
  const { data } = useQuery({ 
    queryKey: ['timeseries', facility.id], 
    queryFn: () => getTimeseries(facility.id, 7) 
  })

  const series = data?.series || []
  const isHigh = facility.historical_emission_rate > 500
  const color = isHigh ? '#ff4444' : '#00aaff'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
      <div style={{ width: '120px', flexShrink: 0 }}>
        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {facility.name}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{facility.historical_emission_rate} kg/hr</div>
      </div>
      <div style={{ flex: 1, height: '40px' }}>
        {series.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series}>
              <YAxis domain={['auto', 'auto']} hide />
              <Area 
                type="monotone" 
                dataKey="emission_rate_kg_hr" 
                stroke={color} 
                fill={color} 
                fillOpacity={0.2} 
                strokeWidth={2} 
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>Loading...</div>
        )}
      </div>
    </div>
  )
}
