import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import Map, { Marker, Source, Layer } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { runLiveScan, geocodeCompany } from '../api/client.js'

export default function DetectionPage() {
  const [formData, setFormData] = useState({
    companyName: '',
    address: '',
    lat: 31.5,
    lon: -103.0,
    radius: 5,
    wind: '',
    maskMode: '',
    preferEmit: false,
    requireLive: true
  })

  const [isDetecting, setIsDetecting] = useState(false)
  const [result, setResult] = useState(null)
  const [images, setImages] = useState({ sat: null, swir: null })
  const abortControllerRef = useRef(null)

  const handleGeocode = async () => {
    if (!formData.companyName && !formData.address) return
    const id = toast.loading('Locating...')
    try {
      const q = formData.address && formData.companyName ? `${formData.address}, ${formData.companyName}` : formData.address || formData.companyName
      const res = await geocodeCompany(q)
      if (res && res.lat && res.lon) {
        setFormData(f => ({ ...f, lat: Number(res.lat), lon: Number(res.lon) }))
        toast.success(`Located: ${res.display_name}`, { id })
      } else {
        toast.error('Location not found', { id })
      }
    } catch (e) {
      toast.error('Geocoding failed', { id })
    }
  }

  const handleDetect = async (e) => {
    e.preventDefault()
    if (isDetecting) {
      abortControllerRef.current?.abort()
      setIsDetecting(false)
      return
    }

    setIsDetecting(true)
    abortControllerRef.current = new AbortController()
    const id = toast.loading('Running Live Scan...')

    try {
      const payload = {
        lat: Number(formData.lat),
        lon: Number(formData.lon),
        radius_km: Number(formData.radius),
        prefer_emit: formData.preferEmit,
        require_live_satellite: formData.requireLive
      }
      if (formData.wind) payload.wind_speed_ms = Number(formData.wind)
      if (formData.maskMode) payload.mask_mode = formData.maskMode

      if (formData.companyName || formData.address) {
        payload.area_name = formData.address || formData.companyName
        payload.max_companies = 20
      }

      const res = await runLiveScan(payload, abortControllerRef.current.signal)
      setResult(res)

      // Fetch images
      const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      const ts = Date.now()
      const plume = res.plume_detected ? 'true' : 'false'
      const q = `?lat=${payload.lat}&lon=${payload.lon}&radius_km=${payload.radius_km}&t=${ts}`
      
      setImages({
        sat: `${API_BASE}/satellite/latest${q}`,
        swir: `${API_BASE}/satellite/swir${q}&plume_detected=${plume}`
      })

      if (res.plume_detected) {
        toast.success('Plume detected!', { id, icon: '🚨' })
      } else {
        toast.success('Scan complete. No plume.', { id, icon: '✅' })
      }

    } catch (err) {
      if (err.name === 'AbortError') {
        toast.error('Scan cancelled', { id })
      } else {
        toast.error('Scan failed', { id })
      }
    } finally {
      setIsDetecting(false)
    }
  }

  // Create bounding box for map
  const r = formData.radius / 111 // rough degree conversion
  const bboxPolygon = {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [formData.lon - r, formData.lat - r],
        [formData.lon + r, formData.lat - r],
        [formData.lon + r, formData.lat + r],
        [formData.lon - r, formData.lat + r],
        [formData.lon - r, formData.lat - r],
      ]]
    }
  }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      
      {/* ── Left Panel: Controls ── */}
      <div style={{
        width: 380, borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', overflowY: 'auto',
        background: 'rgba(8,13,26,0.7)', backdropFilter: 'blur(8px)'
      }}>
        <div style={{ padding: '24px 20px' }}>
          <div className="section-header">
            <span>📡</span><h3>Live Scan Parameters</h3>
          </div>
          
          <form onSubmit={handleDetect} style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
            <div>
              <label style={labelStyle}>COMPANY NAME</label>
              <input className="input" value={formData.companyName} onChange={e => setFormData({...formData, companyName: e.target.value})} placeholder="e.g. Reliance Industries" />
            </div>
            
            <div>
              <label style={labelStyle}>ADDRESS OR REGION</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input className="input" value={formData.address} onChange={e => setFormData({...formData, address: e.target.value})} placeholder="Street, City, Country" />
                <button type="button" onClick={handleGeocode} className="btn btn-ghost" style={{ padding: '0 12px' }}>Locate</button>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={labelStyle}>LATITUDE</label>
                <input type="number" step="any" className="input" value={formData.lat} onChange={e => setFormData({...formData, lat: e.target.value})} required />
              </div>
              <div>
                <label style={labelStyle}>LONGITUDE</label>
                <input type="number" step="any" className="input" value={formData.lon} onChange={e => setFormData({...formData, lon: e.target.value})} required />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={labelStyle}>RADIUS (KM)</label>
                <input type="number" step="0.5" className="input" value={formData.radius} onChange={e => setFormData({...formData, radius: e.target.value})} />
              </div>
              <div>
                <label style={labelStyle}>WIND (M/S)</label>
                <input type="number" step="0.1" className="input" value={formData.wind} onChange={e => setFormData({...formData, wind: e.target.value})} placeholder="Auto" />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={labelStyle}>PREFER EMIT</label>
                <select className="input" value={formData.preferEmit} onChange={e => setFormData({...formData, preferEmit: e.target.value === 'true'})}>
                  <option value="false">No</option>
                  <option value="true">Yes</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>LIVE SATELLITE</label>
                <select className="input" value={formData.requireLive} onChange={e => setFormData({...formData, requireLive: e.target.value === 'true'})}>
                  <option value="true">Strict</option>
                  <option value="false">Allow Fallback</option>
                </select>
              </div>
            </div>

            <button type="submit" className={isDetecting ? "btn btn-danger" : "btn btn-primary"} style={{ marginTop: '8px', justifyContent: 'center', padding: '12px' }}>
              {isDetecting ? 'Cancel Scan' : 'Run Live Scan'}
            </button>
          </form>
        </div>
      </div>

      {/* ── Right Panel: Map & Results ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
        
        {/* Map View */}
        <div style={{ height: '300px', width: '100%', position: 'relative', borderBottom: '1px solid var(--border)' }}>
          <Map
            longitude={Number(formData.lon)}
            latitude={Number(formData.lat)}
            zoom={10}
            onMove={evt => setFormData(f => ({ ...f, lon: evt.viewState.longitude, lat: evt.viewState.latitude }))}
            mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          >
            <Marker longitude={Number(formData.lon)} latitude={Number(formData.lat)} color="var(--neon-green)" />
            <Source id="bbox" type="geojson" data={bboxPolygon}>
              <Layer
                id="bbox-layer"
                type="line"
                paint={{
                  'line-color': '#00aaff',
                  'line-width': 2,
                  'line-dasharray': [2, 2]
                }}
              />
              <Layer
                id="bbox-fill"
                type="fill"
                paint={{
                  'fill-color': '#00aaff',
                  'fill-opacity': 0.1
                }}
              />
            </Source>
          </Map>
          <div style={{ position: 'absolute', top: 12, left: 12, background: 'rgba(0,0,0,0.6)', padding: '6px 10px', borderRadius: 6, fontSize: 11, color: '#fff' }}>
            Interactive Map: Drag to adjust center
          </div>
        </div>

        {/* Results Section */}
        <div style={{ padding: '24px' }}>
          {!result && !isDetecting ? (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '40px' }}>
              Configure parameters and run a scan to see results.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              
              {/* KPIs */}
              {result && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
                  <MetricCard label="Plume Detected" value={result.plume_detected ? 'YES' : 'NO'} color={result.plume_detected ? 'var(--neon-red)' : 'var(--neon-green)'} />
                  <MetricCard label="Emission Rate" value={`${Number(result.emission_kghr || result.quantification?.emission_kghr || 0).toFixed(1)}`} unit="kg/hr" />
                  <MetricCard label="Confidence" value={`${(Number(result.confidence || 0) * 100).toFixed(1)}%`} />
                  <MetricCard label="Financial Cost" value={`$${Number(result.cost_loss_usd_per_hour || result.quantification?.cost_loss_usd_per_hour || 0).toFixed(0)}`} unit="/ hr" />
                </div>
              )}

              {/* Imagery */}
              {(images.sat || images.swir) && (
                <div>
                  <h3 style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '12px' }}>SATELLITE & SWIR IMAGERY</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                    <div style={{ background: '#0a101d', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border)' }}>
                      <div style={{ padding: '8px 12px', fontSize: '11px', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between' }}>
                        <span>RGB VISIBLE</span>
                        <span>Latest Available</span>
                      </div>
                      <img src={images.sat} style={{ width: '100%', display: 'block', minHeight: '200px', objectFit: 'cover' }} alt="RGB" />
                    </div>
                    <div style={{ background: '#0a101d', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border)' }}>
                      <div style={{ padding: '8px 12px', fontSize: '11px', color: 'var(--neon-red)', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', background: 'rgba(255,68,68,0.1)' }}>
                        <span style={{ fontWeight: 600 }}>SWIR METHANE OVERLAY</span>
                        <span>False Color</span>
                      </div>
                      <img src={images.swir} style={{ width: '100%', display: 'block', minHeight: '200px', objectFit: 'cover' }} alt="SWIR" />
                    </div>
                  </div>
                </div>
              )}

              {/* Top Candidates */}
              {result?.attribution?.candidates?.length > 0 && (
                <div>
                  <h3 style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '12px' }}>ATTRIBUTION CANDIDATES</h3>
                  <div className="glass" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {result.attribution.candidates.slice(0, 3).map((c, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>
                        <div>
                          <div style={{ fontWeight: 600 }}>{c.facility_name}</div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{c.facility_type} · {c.distance_km?.toFixed(2)} km away</div>
                        </div>
                        <div style={{ color: 'var(--neon-purple)', fontWeight: 600 }}>
                          {(c.confidence * 100).toFixed(1)}% match
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Raw JSON */}
              {result && (
                <details style={{ cursor: 'pointer', fontSize: '12px' }}>
                  <summary style={{ color: 'var(--neon-blue)', padding: '8px 0' }}>View Raw JSON Data</summary>
                  <pre style={{ background: '#050810', padding: '16px', borderRadius: '8px', border: '1px solid var(--border)', overflowX: 'auto', color: '#aab', marginTop: '8px' }}>
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}

const labelStyle = { fontSize: '10px', color: 'var(--text-secondary)', letterSpacing: '0.08em', display: 'block', marginBottom: '4px' }

function MetricCard({ label, value, unit, color = 'var(--text-primary)' }) {
  return (
    <div className="glass" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
        <span style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color }}>{value}</span>
        {unit && <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{unit}</span>}
      </div>
    </div>
  )
}
