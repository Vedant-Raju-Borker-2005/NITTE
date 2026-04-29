import { useState } from 'react'
import { motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import Map, { Marker, Popup } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import useStore from '../store/useStore.js'
import { getTimeseries, getFacilities } from '../api/client.js'
import { EmissionAreaChart } from '../components/Charts/EmissionChart.jsx'

function RiskBar({ value }) {
  const pct = (value * 100).toFixed(0)
  const color = value > 0.85 ? '#ff4444' : value > 0.7 ? '#ff8c00' : '#ffb300'
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
      <div style={{ flex:1, height:4, background:'var(--bg-elevated)', borderRadius:2, overflow:'hidden' }}>
        <div style={{ width:`${pct}%`, height:'100%', background:color, borderRadius:2, boxShadow:`0 0 4px ${color}80` }} />
      </div>
      <span style={{ fontFamily:'var(--font-mono)', fontSize:11, color, width:30, textAlign:'right' }}>
        {pct}%
      </span>
    </div>
  )
}

export default function FacilitiesPage() {
  const { data: facilitiesData } = useQuery({
    queryKey: ['facilities'],
    queryFn: () => getFacilities(),
    refetchInterval: 60000,
  })
  const facilities = facilitiesData?.facilities || []

  const selectedFacility = useStore(s => s.selectedFacility)
  const setSelectedFacility = useStore(s => s.setSelectedFacility)
  const timeseriesData = useStore(s => s.timeseriesData)
  const setTimeseriesData = useStore(s => s.setTimeseriesData)
  
  const [sortBy, setSortBy] = useState('risk_score')
  const [search, setSearch] = useState('')
  const [selectedType, setSelectedType] = useState('All')
  const [loadingTs, setLoadingTs] = useState(false)
  const [viewMode, setViewMode] = useState('list') // list | map
  const [popupInfo, setPopupInfo] = useState(null)

  const facilityTypes = ['All', ...new Set(facilities.map(f => f.type).filter(Boolean))]

  const filtered = facilities.filter(f => {
    const matchSearch = !search || f.name.toLowerCase().includes(search.toLowerCase()) || (f.country || '').toLowerCase().includes(search.toLowerCase())
    const matchType = selectedType === 'All' || f.type === selectedType
    return matchSearch && matchType
  })

  const sorted = [...filtered].sort((a, b) => (b[sortBy] || 0) - (a[sortBy] || 0))

  const handleSelect = async (fac) => {
    setSelectedFacility(fac)
    setLoadingTs(true)
    if (viewMode === 'map') setPopupInfo(fac)
    try {
      const ts = await getTimeseries(fac.id, 30)
      setTimeseriesData(ts)
    } catch { } finally {
      setLoadingTs(false)
    }
  }

  const exportCsv = () => {
    if (!timeseriesData?.series || !selectedFacility) return
    const csvRows = ['timestamp,emission_rate_kg_hr']
    timeseriesData.series.forEach(d => csvRows.push(`${d.timestamp},${d.emission_rate_kg_hr}`))
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedFacility.name.replace(/\s+/g, '_')}_history.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{ display:'flex', height:'100%', overflow:'hidden' }}>
      {/* ── Facility List ── */}
      <div style={{
        width: 400, borderRight:'1px solid var(--border)',
        display:'flex', flexDirection:'column', overflow:'hidden',
        background:'rgba(8,13,26,0.7)', backdropFilter:'blur(8px)'
      }}>
        {/* Header */}
        <div style={{ padding:'16px 16px 12px', borderBottom:'1px solid var(--border)' }}>
          <div className="section-header" style={{ marginBottom:10, display: 'flex', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', gap: '8px' }}>
              <span>🏭</span><h3>Facility Database</h3>
            </div>
            <span style={{ fontFamily:'var(--font-mono)', fontSize:11, color:'var(--text-secondary)' }}>{filtered.length} total</span>
          </div>

          {/* Search */}
          <input className="input" placeholder="Search facilities or countries…" value={search} onChange={e => setSearch(e.target.value)} style={{ marginBottom:12 }} />

          {/* Type Filter Chips */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: 12 }}>
            {facilityTypes.slice(0, 5).map(type => (
              <button key={type} className={`btn ${selectedType === type ? 'btn-primary' : 'btn-ghost'}`} style={{ padding: '4px 8px', fontSize: 10, borderRadius: '12px' }} onClick={() => setSelectedType(type)}>
                {type.replace(/_/g, ' ')}
              </button>
            ))}
          </div>

          <div style={{ display:'flex', gap:4, justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', gap: 4 }}>
              {[ { key:'risk_score', label:'Risk' }, { key:'historical_emission_rate', label:'Emission' } ].map(s => (
                <button key={s.key} className={`btn ${sortBy === s.key ? 'btn-primary' : 'btn-ghost'}`} style={{ padding:'4px 10px', fontSize:10 }} onClick={() => setSortBy(s.key)}>
                  {s.label}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <button className={`btn ${viewMode === 'list' ? 'btn-primary' : 'btn-ghost'}`} style={{ padding:'4px 10px', fontSize:10 }} onClick={() => setViewMode('list')}>List</button>
              <button className={`btn ${viewMode === 'map' ? 'btn-primary' : 'btn-ghost'}`} style={{ padding:'4px 10px', fontSize:10 }} onClick={() => setViewMode('map')}>Map</button>
            </div>
          </div>
        </div>

        {/* List / Map View */}
        <div style={{ flex:1, overflow:'hidden', display: 'flex', flexDirection: 'column' }}>
          {viewMode === 'list' ? (
            <div style={{ padding:'8px', overflowY: 'auto', flex: 1 }}>
              {sorted.map((fac, i) => (
                <motion.div key={fac.id} initial={{ opacity:0, x:-10 }} animate={{ opacity:1, x:0 }} transition={{ delay:i*0.02 }} onClick={() => handleSelect(fac)}
                  style={{
                    padding:'10px 12px', borderRadius:8, marginBottom:6, cursor:'pointer',
                    background: selectedFacility?.id === fac.id ? 'rgba(0,255,136,0.08)' : 'rgba(13,21,37,0.5)',
                    border: `1px solid ${selectedFacility?.id === fac.id ? 'rgba(0,255,136,0.3)' : 'rgba(68,85,119,0.2)'}`,
                    transition:'all 0.15s'
                  }}>
                  <div style={{ display:'flex', justifyContent:'space-between', marginBottom:5 }}>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {fac.name}
                        {fac.historical_emission_rate > 100 && (
                          <span style={{ background: '#ff4444', color: '#fff', fontSize: '9px', padding: '1px 4px', borderRadius: '4px', textTransform: 'uppercase' }}>Super-Emitter</span>
                        )}
                      </div>
                      <div style={{ fontSize:10, color:'var(--text-secondary)' }}>
                        {fac.type?.replace(/_/g,' ')} · {fac.country}
                      </div>
                    </div>
                    <div style={{ textAlign:'right', marginLeft:8, flexShrink:0 }}>
                      <div style={{ fontFamily:'var(--font-mono)', fontSize:13, fontWeight:700, color: fac.historical_emission_rate > 800 ? 'var(--neon-red)' : 'var(--neon-amber)' }}>
                        {fac.historical_emission_rate}
                      </div>
                      <div style={{ fontSize:9, color:'var(--text-muted)' }}>kg/hr</div>
                    </div>
                  </div>
                  <RiskBar value={fac.risk_score || 0.5} />
                </motion.div>
              ))}
            </div>
          ) : (
            <div style={{ flex: 1 }}>
              <Map
                initialViewState={{ longitude: 0, latitude: 20, zoom: 1 }}
                mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
              >
                {sorted.map(fac => {
                  const color = fac.historical_emission_rate > 800 ? '#ff4444' : fac.historical_emission_rate > 100 ? '#ff8c00' : '#00ff88'
                  return (
                    <Marker key={fac.id} longitude={fac.lon} latitude={fac.lat} onClick={e => { e.originalEvent.stopPropagation(); handleSelect(fac) }}>
                      <div style={{ width: 12, height: 12, background: color, borderRadius: '50%', cursor: 'pointer', boxShadow: `0 0 10px ${color}`, border: '1px solid #fff' }} />
                    </Marker>
                  )
                })}
                {popupInfo && (
                  <Popup longitude={popupInfo.lon} latitude={popupInfo.lat} anchor="top" onClose={() => setPopupInfo(null)} closeOnClick={false}>
                    <div style={{ color: '#000', padding: '4px' }}>
                      <div style={{ fontWeight: 'bold' }}>{popupInfo.name}</div>
                      <div style={{ fontSize: '11px' }}>{popupInfo.historical_emission_rate} kg/hr</div>
                    </div>
                  </Popup>
                )}
              </Map>
            </div>
          )}
        </div>
      </div>

      {/* ── Detail Panel ── */}
      <div style={{ flex:1, overflow:'auto', padding:24, background:'var(--bg-void)' }}>
        {!selectedFacility ? (
          <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'100%', color:'var(--text-muted)', textAlign:'center' }}>
            <div style={{ fontSize:48, marginBottom:16 }}>🏭</div>
            <div style={{ fontSize:16, fontWeight:600, color:'var(--text-secondary)', marginBottom:8 }}>Select a Facility</div>
            <div style={{ fontSize:12 }}>Click any facility to view its emission history and risk profile</div>
          </div>
        ) : (
          <motion.div initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
              <div style={{ flex:1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <h1 style={{ fontSize:24, fontWeight:800, color:'var(--text-primary)', marginBottom:4 }}>{selectedFacility.name}</h1>
                  {selectedFacility.historical_emission_rate > 100 && (
                    <span style={{ background: 'rgba(255, 68, 68, 0.2)', border: '1px solid rgba(255, 68, 68, 0.5)', color: '#ff4444', fontSize: '10px', fontWeight: 800, padding: '4px 8px', borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      🚨 SUPER-EMITTER
                    </span>
                  )}
                </div>
                <div style={{ fontSize:13, color:'var(--text-secondary)', marginTop: '4px' }}>
                  {selectedFacility.type?.replace(/_/g,' ')} · {selectedFacility.country} · {selectedFacility.operator}
                </div>
                <div style={{ fontFamily:'var(--font-mono)', fontSize:12, color:'var(--text-muted)', marginTop:8 }}>
                  {selectedFacility.lat?.toFixed(4)}°N, {selectedFacility.lon?.toFixed(4)}°E
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '12px' }}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontFamily:'var(--font-mono)', fontSize:32, fontWeight:800, color: selectedFacility.risk_score > 0.8 ? 'var(--neon-red)' : 'var(--neon-amber)' }}>
                    {((selectedFacility.risk_score || 0.5) * 100).toFixed(0)}%
                  </div>
                  <div style={{ fontSize:10, color:'var(--text-secondary)', textAlign:'right' }}>RISK SCORE</div>
                </div>
                <button className="btn btn-ghost" onClick={exportCsv} disabled={!timeseriesData} style={{ fontSize: '11px', padding: '6px 12px' }}>
                  📥 Export CSV
                </button>
              </div>
            </div>

            <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:12, marginBottom:20 }}>
              {[
                { label:'Emission Rate', value:`${selectedFacility.historical_emission_rate}`, unit:'kg/hr', color: selectedFacility.historical_emission_rate > 800 ? 'var(--neon-red)' : 'var(--neon-amber)' },
                { label:'Avg (30 days)', value:`${timeseriesData?.average_emission_kg_hr || '-'}`, unit:'kg/hr', color:'var(--neon-green)' },
                { label:'Peak (30 days)', value:`${timeseriesData?.peak_emission_kg_hr || '-'}`, unit:'kg/hr', color:'var(--neon-red)' },
              ].map(m => (
                <div key={m.label} className="metric-card">
                  <div className="metric-label">{m.label}</div>
                  <div className="metric-value" style={{ color:m.color, fontSize:18 }}>{m.value}</div>
                  {m.unit && <div className="metric-sub">{m.unit}</div>}
                </div>
              ))}
            </div>

            <div className="divider" />

            <div style={{ marginBottom:20 }}>
              <div className="section-header">
                <span>📈</span><h3>30-Day Emission History</h3>
              </div>
              {loadingTs ? (
                <div style={{ display:'flex', justifyContent:'center', padding:'40px 0' }}><div className="spinner" /></div>
              ) : timeseriesData ? (
                <>
                  <EmissionAreaChart data={timeseriesData.series || []} height={200} />
                  <div style={{ display: 'flex', gap: 20, marginTop: 12 }}>
                    <div><span style={{ fontSize:11,color:'var(--text-secondary)' }}>Total Methane Released (30d):</span>
                      <span style={{ fontFamily:'var(--font-mono)', fontSize:14, fontWeight: 700, color:'var(--neon-amber)', marginLeft:6 }}>
                        {(timeseriesData.total_emission_kg/1000).toFixed(1)} tons
                      </span>
                    </div>
                  </div>
                </>
              ) : (
                <div style={{ color:'var(--text-muted)', fontSize:12 }}>Select a facility to load timeseries</div>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
