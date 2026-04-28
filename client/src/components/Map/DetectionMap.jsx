import { useRef, useEffect } from 'react'

export default function DetectionMap({ detectionBbox, detectionResult }) {
  const canvasRef = useRef(null)

  // Parse bounding box string
  const parseBbox = (bboxStr) => {
    if (!bboxStr) return null
    const parts = bboxStr.replace(/\s+/g, '').split(',')
    if (parts.length !== 4) return null
    const [lat1, lon1, lat2, lon2] = parts.map(Number)
    return { lat1, lon1, lat2, lon2 }
  }

  useEffect(() => {
    if (!canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const width = canvas.width
    const height = canvas.height

    // Clear with ocean gradient
    const oceanGrad = ctx.createLinearGradient(0, 0, 0, height)
    oceanGrad.addColorStop(0, '#0a1a3a')
    oceanGrad.addColorStop(0.5, '#0d2847')
    oceanGrad.addColorStop(1, '#0f3a5f')
    ctx.fillStyle = oceanGrad
    ctx.fillRect(0, 0, width, height)

    // Utility functions for Mercator projection
    const mercatorX = (lon) => ((lon + 180) / 360) * width
    const mercatorY = (lat) => {
      const latRad = (lat * Math.PI) / 180
      const mercN = Math.log(Math.tan(Math.PI / 4 + latRad / 2))
      return (height / 2) - (height / (2 * Math.PI)) * mercN
    }

    // Draw detailed continents and countries
    const regions = [
      // North America
      { name: 'Canada', lat: 56, lon: -100, w: 350, h: 200, color: '#2d6d4f' },
      { name: 'USA', lat: 40, lon: -100, w: 320, h: 160, color: '#3d7d5f' },
      { name: 'Mexico', lat: 25, lon: -105, w: 140, h: 120, color: '#4a8f6c' },
      // Central America & Caribbean
      { name: 'Central America', lat: 10, lon: -85, w: 100, h: 80, color: '#3d7d5f' },
      // South America
      { name: 'Colombia', lat: 5, lon: -75, w: 80, h: 100, color: '#2a6a4a' },
      { name: 'Brazil', lat: -10, lon: -55, w: 180, h: 200, color: '#1a5a3a' },
      { name: 'Peru', lat: -12, lon: -75, w: 100, h: 140, color: '#2a6a4a' },
      { name: 'Argentina', lat: -35, lon: -65, w: 140, h: 180, color: '#3a7a5a' },
      // Europe
      { name: 'UK', lat: 54, lon: -2, w: 60, h: 80, color: '#4a9f6c' },
      { name: 'France', lat: 47, lon: 2, w: 90, h: 100, color: '#3d8f5f' },
      { name: 'Germany', lat: 51, lon: 10, w: 70, h: 80, color: '#4a9f6c' },
      { name: 'Eastern Europe', lat: 50, lon: 25, w: 150, h: 120, color: '#3a8f5a' },
      { name: 'Spain', lat: 40, lon: -3, w: 80, h: 90, color: '#3d8f5f' },
      { name: 'Italy', lat: 43, lon: 12, w: 60, h: 100, color: '#4a9f6c' },
      // Africa
      { name: 'North Africa', lat: 30, lon: 5, w: 220, h: 120, color: '#d4a85a' },
      { name: 'West Africa', lat: 8, lon: -5, w: 140, h: 160, color: '#3a8a5a' },
      { name: 'Central Africa', lat: 2, lon: 25, w: 180, h: 140, color: '#2a7a4a' },
      { name: 'East Africa', lat: 0, lon: 40, w: 120, h: 200, color: '#3a8a5a' },
      { name: 'Southern Africa', lat: -20, lon: 25, w: 160, h: 160, color: '#4a9a6a' },
      // Middle East
      { name: 'Middle East', lat: 35, lon: 50, w: 140, h: 120, color: '#d4a85a' },
      // Asia
      { name: 'Russia', lat: 60, lon: 90, w: 520, h: 280, color: '#2a6a3a' },
      { name: 'Kazakhstan', lat: 48, lon: 70, w: 180, h: 140, color: '#3a8a5a' },
      { name: 'Central Asia', lat: 42, lon: 68, w: 100, h: 80, color: '#4a8f5c' },
      { name: 'China', lat: 35, lon: 105, w: 300, h: 200, color: '#3d8a5f' },
      { name: 'Mongolia', lat: 48, lon: 105, w: 140, h: 100, color: '#5a9a6a' },
      { name: 'India', lat: 23, lon: 78, w: 160, h: 160, color: '#3a8a5a' },
      { name: 'Southeast Asia', lat: 8, lon: 110, w: 200, h: 160, color: '#1a5a2a' },
      { name: 'Pakistan', lat: 32, lon: 70, w: 100, h: 120, color: '#4a8f5c' },
      { name: 'Japan', lat: 36, lon: 138, w: 80, h: 120, color: '#3d7d5f' },
      { name: 'Korea', lat: 38, lon: 128, w: 60, h: 80, color: '#4a8f5c' },
      // Oceania
      { name: 'Australia', lat: -25, lon: 135, w: 220, h: 240, color: '#d4a85a' },
      { name: 'New Zealand', lat: -41, lon: 173, w: 80, h: 120, color: '#4a9f6c' },
      // Greenland
      { name: 'Greenland', lat: 72, lon: -40, w: 100, h: 160, color: '#e0e0e0' },
    ]

    regions.forEach(region => {
      const x = mercatorX(region.lon)
      const y = mercatorY(region.lat)
      ctx.fillStyle = region.color
      ctx.fillRect(x - region.w / 2, y - region.h / 2, region.w, region.h)
      
      // Border
      ctx.strokeStyle = 'rgba(100, 200, 180, 0.3)'
      ctx.lineWidth = 0.8
      ctx.strokeRect(x - region.w / 2, y - region.h / 2, region.w, region.h)
    })

    // Draw grid lines
    ctx.strokeStyle = 'rgba(100, 200, 255, 0.1)'
    ctx.lineWidth = 1

    // Longitude lines
    for (let lon = -180; lon <= 180; lon += 30) {
      const x = mercatorX(lon)
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, height)
      ctx.stroke()
    }

    // Latitude lines
    for (let lat = -80; lat <= 80; lat += 20) {
      const y = mercatorY(lat)
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(width, y)
      ctx.stroke()
    }

    // Draw equator
    const equatorY = mercatorY(0)
    ctx.strokeStyle = 'rgba(100, 200, 255, 0.2)'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.moveTo(0, equatorY)
    ctx.lineTo(width, equatorY)
    ctx.stroke()

    // Draw detection bbox if provided
    if (detectionBbox) {
      const bbox = parseBbox(detectionBbox)
      if (bbox) {
        const x1 = mercatorX(bbox.lon1)
        const x2 = mercatorX(bbox.lon2)
        const y1 = mercatorY(bbox.lat1)
        const y2 = mercatorY(bbox.lat2)

        // Highlight rectangle
        ctx.fillStyle = 'rgba(0, 255, 136, 0.15)'
        ctx.fillRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1))

        // Border
        ctx.strokeStyle = 'rgba(0, 255, 136, 0.6)'
        ctx.lineWidth = 2.5
        ctx.strokeRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1))

        // Corner markers
        const corners = [[x1, y1], [x2, y1], [x1, y2], [x2, y2]]
        ctx.fillStyle = 'rgba(0, 255, 136, 1)'
        corners.forEach(([cx, cy]) => {
          ctx.fillRect(cx - 3, cy - 3, 6, 6)
        })
      }
    }

    // Draw detection results if available
    if (detectionResult && detectionResult.detected) {
      // Parse center from bbox or use result coordinates
      const bbox = parseBbox(detectionBbox)
      if (bbox) {
        const centerLat = (bbox.lat1 + bbox.lat2) / 2
        const centerLon = (bbox.lon1 + bbox.lon2) / 2
        const x = mercatorX(centerLon)
        const y = mercatorY(centerLat)

        // Large pulsing glow for detection
        const intensity = detectionResult.is_super_emitter ? 1.0 : (detectionResult.emission_rate_kg_hr / 1000 * 0.7)
        
        // Outer glow
        ctx.fillStyle = detectionResult.is_super_emitter ? 'rgba(255, 42, 42, 0.3)' : 'rgba(0, 255, 136, 0.25)'
        ctx.beginPath()
        ctx.arc(x, y, 40 + intensity * 20, 0, Math.PI * 2)
        ctx.fill()

        // Middle glow
        ctx.fillStyle = detectionResult.is_super_emitter ? 'rgba(255, 42, 42, 0.5)' : 'rgba(0, 255, 136, 0.4)'
        ctx.beginPath()
        ctx.arc(x, y, 25 + intensity * 10, 0, Math.PI * 2)
        ctx.fill()

        // Center marker
        ctx.fillStyle = detectionResult.is_super_emitter ? '#ff2a2a' : '#00ff88'
        ctx.beginPath()
        ctx.arc(x, y, 10, 0, Math.PI * 2)
        ctx.fill()

        // Add detection info text
        ctx.fillStyle = detectionResult.is_super_emitter ? '#ff2a2a' : '#00ff88'
        ctx.font = 'bold 12px monospace'
        ctx.textAlign = 'center'
        ctx.fillText(`${detectionResult.emission_rate_kg_hr.toFixed(0)} kg/hr`, x, y - 25)
      }
    }

    // Draw major cities worldwide
    const majorCities = [
      // North America
      { name: 'NYC', lat: 40.7, lon: -74, size: 5 },
      { name: 'LA', lat: 34.1, lon: -118.2, size: 4 },
      { name: 'Chicago', lat: 41.9, lon: -87.6, size: 4 },
      { name: 'Toronto', lat: 43.7, lon: -79.4, size: 4 },
      { name: 'Mexico City', lat: 19.4, lon: -99.1, size: 4 },
      // South America
      { name: 'São Paulo', lat: -23.5, lon: -46.6, size: 4 },
      { name: 'Buenos Aires', lat: -34.6, lon: -58.4, size: 4 },
      { name: 'Rio', lat: -22.9, lon: -43.2, size: 4 },
      { name: 'Lima', lat: -12.0, lon: -77.0, size: 3 },
      // Europe
      { name: 'London', lat: 51.5, lon: 0, size: 4 },
      { name: 'Paris', lat: 48.9, lon: 2.4, size: 4 },
      { name: 'Berlin', lat: 52.5, lon: 13.4, size: 4 },
      { name: 'Madrid', lat: 40.4, lon: -3.7, size: 4 },
      { name: 'Rome', lat: 41.9, lon: 12.5, size: 3 },
      { name: 'Moscow', lat: 55.8, lon: 37.6, size: 4 },
      { name: 'Istanbul', lat: 41.0, lon: 29.0, size: 4 },
      // Middle East & Africa
      { name: 'Cairo', lat: 30.0, lon: 31.2, size: 4 },
      { name: 'Dubai', lat: 25.2, lon: 55.3, size: 4 },
      { name: 'Tehran', lat: 35.7, lon: 51.4, size: 3 },
      { name: 'Lagos', lat: 6.5, lon: 3.4, size: 4 },
      { name: 'Johannesburg', lat: -26.2, lon: 28.0, size: 3 },
      { name: 'Nairobi', lat: -1.3, lon: 36.8, size: 3 },
      // Asia
      { name: 'Beijing', lat: 39.9, lon: 116.4, size: 4 },
      { name: 'Shanghai', lat: 31.2, lon: 121.5, size: 4 },
      { name: 'Hong Kong', lat: 22.3, lon: 114.2, size: 3 },
      { name: 'Bangkok', lat: 13.7, lon: 100.5, size: 4 },
      { name: 'Singapore', lat: 1.3, lon: 103.8, size: 3 },
      { name: 'Delhi', lat: 28.6, lon: 77.2, size: 4 },
      { name: 'Mumbai', lat: 19.1, lon: 72.9, size: 4 },
      { name: 'Tokyo', lat: 35.7, lon: 139.7, size: 4 },
      { name: 'Seoul', lat: 37.6, lon: 126.9, size: 4 },
      // Oceania
      { name: 'Sydney', lat: -33.9, lon: 151.2, size: 3 },
      { name: 'Melbourne', lat: -37.8, lon: 144.9, size: 3 },
      { name: 'Auckland', lat: -37.0, lon: 174.9, size: 3 },
    ]

    ctx.fillStyle = '#ffff99'
    ctx.globalAlpha = 0.7
    majorCities.forEach(city => {
      const x = mercatorX(city.lon)
      const y = mercatorY(city.lat)
      ctx.beginPath()
      ctx.arc(x, y, city.size || 4, 0, Math.PI * 2)
      ctx.fill()
    })
    ctx.globalAlpha = 1

    // Title and legend
    ctx.fillStyle = 'rgba(100, 200, 255, 0.9)'
    ctx.font = 'bold 16px monospace'
    ctx.textAlign = 'left'
    ctx.fillText('🌍 GLOBAL METHANE DETECTION MAP', 16, 28)

    // Enhanced legend
    ctx.font = 'bold 11px monospace'
    ctx.fillStyle = 'rgba(100, 200, 255, 0.8)'
    ctx.fillText('█ Land Mass', 16, height - 70)
    ctx.fillText('■ Detection Region (Green)', 16, height - 52)
    
    ctx.fillStyle = 'rgba(255, 200, 100, 0.8)'
    ctx.fillText('● Major Cities', 16, height - 34)
    
    if (detectionResult && detectionResult.is_super_emitter) {
      ctx.fillStyle = '#ff2a2a'
      ctx.font = 'bold 12px monospace'
      ctx.fillText('★ SUPER-EMITTER', width - 220, 28)
    }
    
    // Coordinates display
    ctx.font = '9px monospace'
    ctx.fillStyle = 'rgba(100, 200, 255, 0.6)'
    ctx.textAlign = 'right'
    ctx.fillText('North: 85°N  |  South: 85°S  |  East: 180°E  |  West: 180°W', width - 16, height - 12)
  }, [detectionBbox, detectionResult])

  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: '#050810',
      position: 'relative',
      overflow: 'hidden'
    }}>
      <canvas
        ref={canvasRef}
        width={1200}
        height={700}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
          backgroundColor: '#0a0f1a'
        }}
      />

      {/* Status overlay */}
      {detectionResult && (
        <div style={{
          position: 'absolute',
          top: 16,
          right: 16,
          backgroundColor: detectionResult.detected ? 'rgba(0, 255, 136, 0.1)' : 'rgba(100, 100, 150, 0.1)',
          border: `1px solid ${detectionResult.detected ? 'rgba(0, 255, 136, 0.5)' : 'rgba(100, 100, 150, 0.5)'}`,
          borderRadius: 8,
          padding: '12px 16px',
          backdropFilter: 'blur(8px)',
          maxWidth: 220
        }}>
          <div style={{
            fontSize: 11,
            fontWeight: 700,
            color: detectionResult.detected ? '#00ff88' : '#888888',
            letterSpacing: '0.1em',
            marginBottom: 6
          }}>
            {detectionResult.detected ? '🔴 PLUME DETECTED' : '✅ NO PLUME'}
          </div>
          <div style={{ fontSize: 10, color: 'rgba(200, 220, 255, 0.6)' }}>
            Emission: {detectionResult.emission_rate_kg_hr?.toFixed(1)} kg/hr
          </div>
          <div style={{ fontSize: 10, color: 'rgba(200, 220, 255, 0.6)' }}>
            Confidence: {(detectionResult.detection_confidence * 100)?.toFixed(1)}%
          </div>
          {detectionResult.is_super_emitter && (
            <div style={{ fontSize: 10, color: '#ff2a2a', marginTop: 6, fontWeight: 700 }}>
              ⚠️ SUPER-EMITTER
            </div>
          )}
        </div>
      )}
    </div>
  )
}
