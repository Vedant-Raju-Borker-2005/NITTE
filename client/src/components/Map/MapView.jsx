import { useMemo, useState, useCallback } from 'react'
import useStore from '../../store/useStore.js'

// Lazy load deck.gl to avoid SSR/Vite issues
let DeckGL, ScatterplotLayer, HeatmapLayer, PolygonLayer, Map, deck
let isLoaded = false
let loadPromise = null

const loadDeck = () => {
  if (isLoaded) return Promise.resolve()
  if (loadPromise) return loadPromise
  loadPromise = Promise.all([
    import('@deck.gl/react'),
    import('@deck.gl/layers'),
    import('react-map-gl/maplibre'),
    import('maplibre-gl/dist/maplibre-gl.css' + ''),
  ]).then(([deckReact, deckLayers, mapGl]) => {
    DeckGL = deckReact.default
    ScatterplotLayer = deckLayers.ScatterplotLayer
    HeatmapLayer = deckLayers.HeatmapLayer
    PolygonLayer = deckLayers.PolygonLayer
    Map = mapGl.Map
    isLoaded = true
  }).catch(err => {
    console.warn('deck.gl load failed, using fallback:', err.message)
  })
  return loadPromise
}

const INITIAL_VIEW = {
  longitude: 0,
  latitude: 20,
  zoom: 2,
  pitch: 30,
  bearing: 0,
}

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

// Simple Canvas fallback map when deck.gl unavailable
function FallbackMap({ heatmapData, facilities, detectionResult }) {
  const hotspots = heatmapData?.hotspots || []

  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative',
      background: 'linear-gradient(180deg, #050810 0%, #080d1a 50%, #050810 100%)',
    }}>
      {/* Simulated world map grid */}
      <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0 }}>
        <defs>
          <pattern id="grid" width="60" height="40" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 40" fill="none" stroke="rgba(0,170,255,0.06)" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />

        {/* Simplified continental shapes */}
        <g>
          {/* North America */}
          <ellipse cx="18%" cy="38%" rx="8%" ry="12%" fill="rgba(17,34,64,0.8)" stroke="rgba(0,170,255,0.15)" strokeWidth="1"/>
          {/* South America */}
          <ellipse cx="22%" cy="62%" rx="5%" ry="9%" fill="rgba(17,34,64,0.8)" stroke="rgba(0,170,255,0.15)" strokeWidth="1"/>
          {/* Europe */}
          <ellipse cx="47%" cy="30%" rx="5%" ry="6%" fill="rgba(17,34,64,0.8)" stroke="rgba(0,170,255,0.15)" strokeWidth="1"/>
          {/* Africa */}
          <ellipse cx="50%" cy="57%" rx="6%" ry="10%" fill="rgba(17,34,64,0.8)" stroke="rgba(0,170,255,0.15)" strokeWidth="1"/>
          {/* Asia */}
          <ellipse cx="68%" cy="35%" rx="13%" ry="12%" fill="rgba(17,34,64,0.8)" stroke="rgba(0,170,255,0.15)" strokeWidth="1"/>
          {/* Australia */}
          <ellipse cx="78%" cy="65%" rx="6%" ry="5%" fill="rgba(17,34,64,0.8)" stroke="rgba(0,170,255,0.15)" strokeWidth="1"/>
        </g>

        {/* Hotspot markers */}
        {hotspots.map((h, i) => {
          const x = ((h.lon + 180) / 360) * 100
          const y = ((90 - h.lat) / 180) * 100
          const r = 4 + h.intensity * 12
          const color = h.intensity > 0.8 ? '#ff2222' : h.intensity > 0.5 ? '#ff8800' : '#ffcc00'
          return (
            <g key={i}>
              <circle cx={`${x}%`} cy={`${y}%`} r={r * 2} fill={color} opacity={0.1}>
                <animate attributeName="r" values={`${r*2};${r*3};${r*2}`} dur="2s" repeatCount="indefinite"/>
              </circle>
              <circle cx={`${x}%`} cy={`${y}%`} r={r * 0.6} fill={color} opacity={0.9}/>
            </g>
          )
        })}

        {/* Detection bbox overlay */}
        {detectionResult?.plume_pixels?.slice(0, 100).map((p, i) => {
          const x = ((p.lon + 180) / 360) * 100
          const y = ((90 - p.lat) / 180) * 100
          return <circle key={i} cx={`${x}%`} cy={`${y}%`} r="3" fill="#00ff88" opacity="0.7"/>
        })}
      </svg>

      {/* Map label */}
      <div style={{
        position: 'absolute', bottom: 16, left: 16,
        fontSize: 11, color: 'var(--text-secondary)',
        background: 'rgba(13,21,37,0.7)', padding: '4px 8px', borderRadius: 4,
      }}>
        Global Methane Emissions Map · {hotspots.length} monitored sites
      </div>

      {/* Legend */}
      <div style={{
        position: 'absolute', bottom: 16, right: 16,
        background: 'rgba(13,21,37,0.85)', backdropFilter: 'blur(8px)',
        border: '1px solid rgba(0,170,255,0.2)', borderRadius: 8,
        padding: '10px 14px', fontSize: 11, color: '#8899bb', lineHeight: 1.8
      }}>
        <div style={{ fontWeight: 700, color: '#e8f0fe', marginBottom: 4 }}>EMISSION INTENSITY</div>
        <div>🔴 &gt;800 kg/hr (Critical)</div>
        <div>🟠 400–800 kg/hr (High)</div>
        <div>🟡 100–400 kg/hr (Med)</div>
        {detectionResult?.detected && <div style={{ color: '#00ff88' }}>■ Detected Plume</div>}
      </div>
    </div>
  )
}

export default function MapView({ onFacilityClick }) {
  const heatmapData = useStore(s => s.heatmapData)
  const detectionResult = useStore(s => s.detectionResult)
  const facilities = useStore(s => s.facilities)

  // Always use the SVG fallback map - reliable, no external deps
  return (
    <FallbackMap
      heatmapData={heatmapData}
      facilities={facilities}
      detectionResult={detectionResult}
    />
  )
}
