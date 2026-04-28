import { useState } from 'react'
import Map, { Marker, Popup } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

export default function MapLibreView({ hotspots = [] }) {
  const [popupInfo, setPopupInfo] = useState(null)

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <Map
        initialViewState={{
          longitude: 0,
          latitude: 20,
          zoom: 1.5
        }}
        mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
      >
        {hotspots.map((spot, i) => {
          let color = '#44ff88'
          if (spot.level === 'high') color = '#ff2a2a'
          else if (spot.level === 'medium') color = '#ff8c00'
          else if (spot.level === 'low') color = '#ffb300'
          
          return (
            <Marker
              key={i}
              longitude={spot.lon}
              latitude={spot.lat}
              anchor="center"
              onClick={e => {
                e.originalEvent.stopPropagation()
                setPopupInfo(spot)
              }}
            >
              <div style={{
                width: 12 + (spot.intensity || 0) * 8,
                height: 12 + (spot.intensity || 0) * 8,
                background: color,
                borderRadius: '50%',
                cursor: 'pointer',
                boxShadow: `0 0 10px ${color}`
              }} />
            </Marker>
          )
        })}

        {popupInfo && (
          <Popup
            anchor="top"
            longitude={popupInfo.lon}
            latitude={popupInfo.lat}
            onClose={() => setPopupInfo(null)}
            closeOnClick={false}
          >
            <div style={{ color: '#000', padding: '4px', minWidth: '150px' }}>
              <div style={{ fontWeight: 'bold', fontSize: '14px', marginBottom: '4px' }}>
                {popupInfo.region}
              </div>
              <div style={{ fontSize: '12px', marginBottom: '8px' }}>
                Rate: {popupInfo.emission_rate_kg_hr.toFixed(1)} kg/hr
              </div>
              <div style={{ 
                display: 'inline-block',
                background: popupInfo.level === 'high' ? '#ff2a2a' : popupInfo.level === 'medium' ? '#ff8c00' : '#ffb300',
                color: '#fff',
                padding: '2px 6px',
                borderRadius: '4px',
                fontSize: '10px',
                fontWeight: 'bold',
                textTransform: 'uppercase'
              }}>
                {popupInfo.level} Severity
              </div>
              <div style={{ marginTop: '8px' }}>
                <a href={`/facilities?id=${popupInfo.id}`} style={{ color: '#0066cc', textDecoration: 'none', fontSize: '12px', fontWeight: 'bold' }}>
                  View details →
                </a>
              </div>
            </div>
          </Popup>
        )}
      </Map>
    </div>
  )
}
