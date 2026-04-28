import { useState, Suspense, useEffect } from 'react'
import Globe from '../components/Globe/Globe.jsx'
import MapLibreView from '../components/Map/MapLibreView.jsx'
import AlertPanel from '../components/Alerts/AlertPanel.jsx'
import { GlobalTrendChart } from '../components/Charts/EmissionChart.jsx'
import useStore from '../store/useStore.js'
import { getGlobalTimeseries } from '../api/client.js'

export default function GlobePage() {
  const heatmapData = useStore(s => s.heatmapData)
  const topPolluters = useStore(s => s.topPolluters)
  const setGlobalTimeseries = useStore(s => s.setGlobalTimeseries)
  const globalTimeseries = useStore(s => s.globalTimeseries)
  const [view, setView] = useState('globe') // 'globe' | 'map'

  useEffect(() => {
    if (!globalTimeseries) {
      getGlobalTimeseries(30).then(d => setGlobalTimeseries(d.series)).catch(console.warn)
    }
  }, [])

  const hotspots = heatmapData?.hotspots || []

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* ── Left: 3D Globe ── */}
      <div style={{ flex: 1, position: 'relative', minWidth: 0 }}>
        {/* View Toggle */}
        <div style={{
          position: 'absolute', top: 16, left: 16, zIndex: 10,
          display: 'flex', gap: 6
        }}>
          {['globe', 'map', 'stats'].map(v => (
            <button
              key={v}
              className={`btn ${view === v ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setView(v)}
              style={{ padding: '6px 14px', fontSize: 11 }}
            >
              {v === 'globe' ? '🌍 3D Globe' : v === 'map' ? '🗺️ 2D Map' : '📊 Stats'}
            </button>
          ))}
        </div>

        {view === 'globe' ? (
          <Suspense fallback={<div style={{ display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:'var(--text-secondary)'}}>Loading 3D Globe…</div>}>
            <Globe hotspots={hotspots} />
          </Suspense>
        ) : view === 'map' ? (
          <Suspense fallback={<div style={{ display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:'var(--text-secondary)'}}>Loading Map…</div>}>
            <MapLibreView hotspots={hotspots} />
          </Suspense>
        ) : (
          <div style={{ padding: '80px 24px 24px 24px', height: '100%', overflow: 'auto' }}>
            <GlobalStatsView hotspots={hotspots} timeseries={globalTimeseries} />
          </div>
        )}

        {/* Bottom emission ticker */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          background: 'rgba(8,13,26,0.9)', borderTop: '1px solid var(--border)',
          padding: '8px 20px', display: 'flex', alignItems: 'center', gap: 24,
          overflow: 'hidden'
        }}>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing:'0.1em', color:'var(--text-muted)', flexShrink:0 }}>
            EMISSION TICKER
          </span>
          <div style={{ display: 'flex', gap: 20, overflow: 'hidden' }}>
            {hotspots.slice(0, 8).map((h, i) => (
              <span key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: 11, whiteSpace: 'nowrap' }}>
                <span style={{ color: 'var(--text-secondary)' }}>{h.region}</span>
                <span style={{ color: h.intensity > 0.7 ? 'var(--neon-red)' : 'var(--neon-amber)', marginLeft: 6 }}>
                  {h.emission_rate_kg_hr.toFixed(0)} kg/hr
                </span>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ── Right sidebar ── */}
      <div style={{
        width: 300, borderLeft: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        background: 'rgba(8,13,26,0.6)', backdropFilter: 'blur(8px)'
      }}>
        {/* Top Polluters */}
        <div style={{ padding: 16, borderBottom: '1px solid var(--border)', flex: 1, overflow: 'auto' }}>
          <div className="section-header">
            <span style={{ fontSize: 16 }}>🏭</span>
            <h3>Top Polluters</h3>
          </div>
          {topPolluters.slice(0, 10).map((fac, i) => (
            <div key={fac.id} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '8px 0', borderBottom: '1px solid rgba(68,85,119,0.15)'
            }}>
              <span style={{
                width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                background: i < 3 ? 'rgba(255,68,68,0.15)' : 'rgba(255,140,0,0.1)',
                border: `1px solid ${i < 3 ? '#ff4444' : '#ff8c00'}40`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 9, fontWeight: 800, color: i < 3 ? '#ff4444' : '#ff8c00'
              }}>{i + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {fac.name}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                  {fac.country}
                </div>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
                color: fac.historical_emission_rate > 800 ? 'var(--neon-red)' : 'var(--neon-amber)',
                flexShrink: 0 }}>
                {fac.historical_emission_rate} <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>kg/hr</span>
              </div>
            </div>
          ))}
        </div>

        {/* Live Alerts */}
        <div style={{ padding: 16, height: 240, overflow: 'auto', flexShrink: 0 }}>
          <AlertPanel maxItems={5} />
        </div>
      </div>
    </div>
  )
}

function GlobalStatsView({ hotspots, timeseries }) {
  // Calculate stats based on actual data levels
  const total = hotspots.reduce((s, h) => s + (h.emission_rate_kg_hr || 0), 0)
  
  // Simple direct filtering by level field
  const critical = hotspots.filter(h => h.level === 'high').length
  const high = hotspots.filter(h => h.level === 'medium').length
  const medium = hotspots.filter(h => h.level === 'low').length

  return (
    <div style={{ maxWidth: 700 }}>
      <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 20, color: 'var(--text-primary)' }}>
        Global Methane Overview
      </h2>
      
      {/* Top metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
        {[
          { label: 'Total Monitored Rate', value: `${(total/1000).toFixed(1)}k`, unit: 'kg/hr', color: 'var(--neon-amber)' },
          { label: 'CO₂ Equivalent', value: `${(total * 84 / 1000).toFixed(1)}k`, unit: 'kg/hr (GWP-20)', color: 'var(--neon-purple)' },
          { label: 'Total Hotspots', value: hotspots.length, unit: 'detected', color: 'var(--neon-blue)' },
        ].map(m => (
          <div key={m.label} className="metric-card">
            <div className="metric-label">{m.label}</div>
            <div className="metric-value" style={{ color: m.color }}>{m.value}</div>
            <div className="metric-sub">{m.unit}</div>
          </div>
        ))}
      </div>

      {/* Severity breakdown - matches alerts section */}
      <div style={{ padding: 16, background: 'rgba(0,170,255,0.05)', borderRadius: 8, border: '1px solid rgba(0,170,255,0.1)' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>Alert Severity Distribution</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          <div style={{ padding: 12, background: 'rgba(255,26,26,0.08)', borderRadius: 6, border: '1px solid #ff1a1a80' }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>🔴 CRITICAL</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#ff1a1a' }}>{critical}</div>
          </div>
          <div style={{ padding: 12, background: 'rgba(255,140,0,0.08)', borderRadius: 6, border: '1px solid #ff8c0080' }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>🟠 HIGH</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#ff8c00' }}>{high}</div>
          </div>
          <div style={{ padding: 12, background: 'rgba(255,179,0,0.08)', borderRadius: 6, border: '1px solid #ffb30080' }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>🟡 MEDIUM</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#ffb300' }}>{medium}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
