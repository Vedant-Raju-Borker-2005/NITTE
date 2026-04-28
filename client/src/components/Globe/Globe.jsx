import { useRef, useEffect, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls, Stars, Html } from '@react-three/drei'
import * as THREE from 'three'
import useStore from '../../store/useStore.js'

// Real-world locations for labels
const REAL_LOCATIONS = [
  // Major cities
  { name: 'New York', lat: 40.7128, lon: -74.0060, type: 'city' },
  { name: 'London', lat: 51.5074, lon: -0.1278, type: 'city' },
  { name: 'Tokyo', lat: 35.6762, lon: 139.6503, type: 'city' },
  { name: 'Sydney', lat: -33.8688, lon: 151.2093, type: 'city' },
  { name: 'Dubai', lat: 25.2048, lon: 55.2708, type: 'city' },
  { name: 'Shanghai', lat: 31.2304, lon: 121.4737, type: 'city' },
  { name: 'Singapore', lat: 1.3521, lon: 103.8198, type: 'city' },
  { name: 'Mumbai', lat: 19.0760, lon: 72.8777, type: 'city' },
  { name: 'São Paulo', lat: -23.5505, lon: -46.6333, type: 'city' },
  { name: 'Lagos', lat: 6.5244, lon: 3.3792, type: 'city' },
  
  // Major methane regions
  { name: 'Permian Basin', lat: 31.5, lon: -103, type: 'region', risk: 'high' },
  { name: 'Bakken', lat: 47.5, lon: -103, type: 'region', risk: 'high' },
  { name: 'Alberta', lat: 53, lon: -115, type: 'region', risk: 'high' },
  { name: 'North Sea', lat: 55, lon: 2, type: 'region', risk: 'medium' },
  { name: 'Caspian Sea', lat: 42, lon: 52, type: 'region', risk: 'high' },
  { name: 'Middle East', lat: 25, lon: 50, type: 'region', risk: 'high' },
  { name: 'West Siberia', lat: 65, lon: 75, type: 'region', risk: 'high' },
  { name: 'South China Sea', lat: 10, lon: 110, type: 'region', risk: 'medium' },
]

// Label component for locations
function LocationLabel({ location, zoomLevel }) {
  const [hovered, setHovered] = useState(false)
  
  // Show labels only when sufficiently zoomed in
  if (zoomLevel > 4) return null

  const phi = (90 - location.lat) * (Math.PI / 180)
  const theta = (location.lon + 180) * (Math.PI / 180)
  const r = 1.08
  const x = -r * Math.sin(phi) * Math.cos(theta)
  const y = r * Math.cos(phi)
  const z = r * Math.sin(phi) * Math.sin(theta)

  const isRegion = location.type === 'region'
  const color = isRegion && location.risk === 'high' ? '#ff3344' : isRegion ? '#ffaa33' : '#66ff88'
  const size = hovered ? 0.12 : 0.08

  return (
    <group position={[x, y, z]} onPointerOver={() => setHovered(true)} onPointerOut={() => setHovered(false)}>
      <mesh>
        <sphereGeometry args={[size, 8, 8]} />
        <meshBasicMaterial color={color} emissive={color} emissiveIntensity={hovered ? 1 : 0.5} />
      </mesh>
    </group>
  )
}
// ── Globe Sphere with real Earth texture ────────────────────────────────────
function EarthGlobe({ hotspots = [], geojsonData = null }) {
  const meshRef = useRef()
  const atmosphereRef = useRef()
  const countryLinesRef = useRef()
  const textureRef = useRef(null)

  useFrame(({ clock }) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = clock.getElapsedTime() * 0.02
    }
    if (atmosphereRef.current) {
      atmosphereRef.current.rotation.y = clock.getElapsedTime() * 0.021
    }
    if (countryLinesRef.current) {
      countryLinesRef.current.rotation.y = clock.getElapsedTime() * 0.02
    }
  })

  // Load real-world Earth texture
  useEffect(() => {
    const textureLoader = new THREE.TextureLoader()
    
    // Use NASA Blue Marble or similar real satellite imagery
    // This is a placeholder - you can use any real Earth texture URL
    textureLoader.load(
      'https://tile.openstreetmap.org/0/0/0.png', // Fallback
      (texture) => {
        if (textureRef.current) {
          textureRef.current.dispose()
        }
        texture.magFilter = THREE.LinearFilter
        texture.minFilter = THREE.LinearMipmapLinearFilter
        textureRef.current = texture
      },
      undefined,
      () => {
        // Fallback: create a high-quality procedural Earth
        createEnhancedEarth()
      }
    )

    // Always create enhanced Earth as backup/primary
    createEnhancedEarth()

    return () => {
      if (textureRef.current) {
        textureRef.current.dispose()
      }
    }
  }, [])

  // Create enhanced procedural Earth with realistic colors
  const createEnhancedEarth = () => {
    const canvas = document.createElement('canvas')
    canvas.width = 4096
    canvas.height = 2048
    const ctx = canvas.getContext('2d')

    // Deep ocean
    const oceanGrad = ctx.createLinearGradient(0, 0, 0, 2048)
    oceanGrad.addColorStop(0, '#0a1929')
    oceanGrad.addColorStop(0.3, '#0f3a5f')
    oceanGrad.addColorStop(0.7, '#0f3a5f')
    oceanGrad.addColorStop(1, '#0a1929')
    ctx.fillStyle = oceanGrad
    ctx.fillRect(0, 0, 4096, 2048)

    // Add realistic continent colors
    const landColor1 = '#2d6a3e' // Forest green
    const landColor2 = '#3d8b4f' // Lighter green
    const desertColor = '#a98d5f' // Desert tan
    const mountainColor = '#5a5a5a' // Gray

    // Create more detailed coastlines and regions with realistic country variation
    const regions = [
      // North America - detailed countries
      { lat: 48, lon: -100, width: 280, height: 200, color: '#2d6a3e' },
      { lat: 38, lon: -105, width: 320, height: 160, color: '#3d8b4f' },
      { lat: 28, lon: -100, width: 240, height: 120, color: '#a98d5f' },
      // Canada
      { lat: 60, lon: -95, width: 300, height: 180, color: '#1f5030' },
      // Mexico
      { lat: 18, lon: -100, width: 200, height: 120, color: '#2d6a3e' },
      // Central America - Guatemala, Honduras, Belize
      { lat: 14, lon: -88, width: 120, height: 100, color: '#3d8b4f' },
      // South America - Colombia, Venezuela
      { lat: 8, lon: -70, width: 200, height: 140, color: '#2d6a3e' },
      // Amazon Brazil
      { lat: -2, lon: -62, width: 280, height: 200, color: '#1f5030' },
      // Peru, Bolivia
      { lat: -12, lon: -70, width: 180, height: 160, color: '#3d8b4f' },
      // Argentina, Paraguay
      { lat: -32, lon: -65, width: 200, height: 160, color: '#2d6a3e' },
      // Chile
      { lat: -35, lon: -72, width: 100, height: 220, color: '#5a5a5a' },
      // Greenland
      { lat: 72, lon: -40, width: 140, height: 160, color: '#909090' },
      // Iceland
      { lat: 65, lon: -18, width: 60, height: 60, color: '#4a4a4a' },
      // UK
      { lat: 54, lon: -2, width: 100, height: 80, color: '#2d6a3e' },
      // France, Benelux
      { lat: 48, lon: 2, width: 150, height: 100, color: '#3d8b4f' },
      // Spain, Portugal
      { lat: 40, lon: -2, width: 120, height: 90, color: '#a98d5f' },
      // Germany, Poland, Scandinavia
      { lat: 55, lon: 15, width: 180, height: 120, color: '#2d6a3e' },
      // Italy, Balkans
      { lat: 42, lon: 15, width: 100, height: 100, color: '#3d8b4f' },
      // Greece, Turkey
      { lat: 39, lon: 27, width: 120, height: 100, color: '#5a5a5a' },
      // Russia - European
      { lat: 55, lon: 40, width: 250, height: 140, color: '#1f5030' },
      // Russia - Urals
      { lat: 58, lon: 60, width: 200, height: 120, color: '#2d6a3e' },
      // Russia - Siberia
      { lat: 65, lon: 100, width: 400, height: 180, color: '#2d6a3e' },
      // Russia - Far East
      { lat: 58, lon: 150, width: 240, height: 140, color: '#3d8b4f' },
      // North Africa - Morocco, Algeria
      { lat: 32, lon: 0, width: 280, height: 180, color: '#c4a47a' },
      // Egypt
      { lat: 26, lon: 30, width: 120, height: 140, color: '#a98d5f' },
      // Mali, Mauritania
      { lat: 18, lon: -8, width: 200, height: 140, color: '#b8956a' },
      // West Africa - Nigeria, Ghana
      { lat: 8, lon: 5, width: 200, height: 160, color: '#2d6a3e' },
      // Central Africa - Congo, CAR
      { lat: 3, lon: 20, width: 220, height: 200, color: '#1f5030' },
      // East Africa - Ethiopia, Kenya
      { lat: 5, lon: 40, width: 200, height: 220, color: '#2d6a3e' },
      // Southern Africa - Zimbabwe, Botswana
      { lat: -18, lon: 28, width: 200, height: 180, color: '#3d8b4f' },
      // South Africa
      { lat: -30, lon: 25, width: 140, height: 140, color: '#a98d5f' },
      // Turkey
      { lat: 39, lon: 35, width: 140, height: 100, color: '#a98d5f' },
      // Syria, Lebanon
      { lat: 35, lon: 38, width: 100, height: 80, color: '#b8956a' },
      // Saudi Arabia, Yemen
      { lat: 24, lon: 48, width: 200, height: 160, color: '#c4a47a' },
      // UAE, Oman
      { lat: 22, lon: 55, width: 120, height: 100, color: '#b8956a' },
      // Iran
      { lat: 32, lon: 55, width: 160, height: 140, color: '#a98d5f' },
      // Afghanistan, Tajikistan
      { lat: 35, lon: 68, width: 160, height: 120, color: '#5a5a5a' },
      // Kazakhstan, Kyrgyzstan, Uzbekistan
      { lat: 42, lon: 65, width: 240, height: 140, color: '#8b7355' },
      // Tibet, Mongolia
      { lat: 36, lon: 95, width: 320, height: 180, color: '#4a4a4a' },
      // Pakistan, Kashmir
      { lat: 32, lon: 75, width: 140, height: 120, color: '#2d6a3e' },
      // India
      { lat: 23, lon: 78, width: 160, height: 140, color: '#3d8b4f' },
      // Nepal, Bhutan
      { lat: 28, lon: 84, width: 120, height: 80, color: '#5a5a5a' },
      // Bangladesh
      { lat: 24, lon: 90, width: 100, height: 90, color: '#2d6a3e' },
      // Myanmar
      { lat: 20, lon: 98, width: 100, height: 110, color: '#1f5030' },
      // Thailand, Laos
      { lat: 15, lon: 105, width: 140, height: 100, color: '#2d6a3e' },
      // Vietnam, Cambodia
      { lat: 15, lon: 108, width: 120, height: 140, color: '#3d8b4f' },
      // Malaysia
      { lat: 5, lon: 105, width: 100, height: 140, color: '#2d6a3e' },
      // Indonesia
      { lat: -3, lon: 117, width: 240, height: 160, color: '#1f5030' },
      // Philippines
      { lat: 12, lon: 122, width: 120, height: 140, color: '#2d6a3e' },
      // China
      { lat: 35, lon: 105, width: 320, height: 220, color: '#3d8b4f' },
      // Japan
      { lat: 38, lon: 138, width: 120, height: 160, color: '#2d6a3e' },
      // South Korea
      { lat: 37, lon: 127, width: 100, height: 100, color: '#3d8b4f' },
      // North Korea
      { lat: 41, lon: 127, width: 80, height: 80, color: '#2d6a3e' },
      // Australia
      { lat: -25, lon: 135, width: 240, height: 240, color: '#a98d5f' },
      // Papua New Guinea
      { lat: -6, lon: 147, width: 140, height: 120, color: '#2d6a3e' },
      // New Zealand
      { lat: -41, lon: 175, width: 100, height: 120, color: '#3d8b4f' },
    ]

    regions.forEach(region => {
      const x = ((region.lon + 180) / 360) * 4096
      const y = ((90 - region.lat) / 180) * 2048
      ctx.fillStyle = region.color
      ctx.fillRect(x - region.width / 2, y - region.height / 2, region.width, region.height)
    })

    // Add coastal details with varying opacity
    ctx.globalAlpha = 0.5
    ctx.fillStyle = '#1a4a28'
    for (let i = 0; i < 600; i++) {
      const x = Math.random() * 4096
      const y = Math.random() * 2048
      const width = Math.random() * 150 + 40
      const height = Math.random() * 120 + 30
      ctx.fillRect(x, y, width, height)
    }
    ctx.globalAlpha = 1

    // Draw country border indicators as subtle lines
    ctx.strokeStyle = 'rgba(100, 255, 180, 0.3)'
    ctx.lineWidth = 1.5
    // Major country boundary markers - longitude based
    for (let lon = -180; lon < 180; lon += 20) {
      const x = ((lon + 180) / 360) * 4096
      ctx.beginPath()
      ctx.moveTo(x, 400)
      ctx.lineTo(x, 1650)
      ctx.stroke()
    }
    // Latitude country boundaries
    for (let lat = 60; lat > -60; lat -= 15) {
      const y = ((90 - lat) / 180) * 2048
      ctx.beginPath()
      ctx.moveTo(800, y)
      ctx.lineTo(3296, y)
      ctx.stroke()
    }

    // Enhanced grid with better spacing
    ctx.strokeStyle = 'rgba(100, 200, 255, 0.08)'
    ctx.lineWidth = 1
    
    // Longitude lines
    for (let i = 0; i < 37; i++) {
      ctx.beginPath()
      ctx.moveTo(i * 110.65, 0)
      ctx.lineTo(i * 110.65, 2048)
      ctx.stroke()
    }
    
    // Latitude lines
    for (let j = 0; j < 19; j++) {
      ctx.beginPath()
      ctx.moveTo(0, j * 107.8)
      ctx.lineTo(4096, j * 107.8)
      ctx.stroke()
    }

    // Add subtle cloud layer effect
    ctx.globalAlpha = 0.08
    ctx.fillStyle = '#ffffff'
    for (let i = 0; i < 200; i++) {
      const x = Math.random() * 4096
      const y = Math.random() * 2048
      const size = Math.random() * 200 + 50
      ctx.fillRect(x, y, size, size)
    }
    ctx.globalAlpha = 1

    textureRef.current = new THREE.CanvasTexture(canvas)
    textureRef.current.magFilter = THREE.LinearFilter
    textureRef.current.minFilter = THREE.LinearMipmapLinearFilter
  }

  // Create country border lines from GeoJSON
  useEffect(() => {
    if (!geojsonData || !countryLinesRef.current) return

    const lineGeometry = new THREE.BufferGeometry()
    const positions = []

    try {
      geojsonData.features.forEach(feature => {
        if (feature.geometry.type === 'Polygon') {
          feature.geometry.coordinates.forEach(ring => {
            ring.forEach((coord, idx) => {
              const [lon, lat] = coord
              const phi = (90 - lat) * (Math.PI / 180)
              const theta = (lon + 180) * (Math.PI / 180)
              const x = -Math.sin(phi) * Math.cos(theta) * 1.001
              const y = Math.cos(phi) * 1.001
              const z = Math.sin(phi) * Math.sin(theta) * 1.001
              positions.push(x, y, z)
            })
          })
        } else if (feature.geometry.type === 'MultiPolygon') {
          feature.geometry.coordinates.forEach(polygon => {
            polygon.forEach(ring => {
              ring.forEach((coord, idx) => {
                const [lon, lat] = coord
                const phi = (90 - lat) * (Math.PI / 180)
                const theta = (lon + 180) * (Math.PI / 180)
                const x = -Math.sin(phi) * Math.cos(theta) * 1.001
                const y = Math.cos(phi) * 1.001
                const z = Math.sin(phi) * Math.sin(theta) * 1.001
                positions.push(x, y, z)
              })
            })
          })
        }
      })

      lineGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3))
      
      const lineMaterial = new THREE.LineBasicMaterial({
        color: 0x00ff99,
        linewidth: 3,
        transparent: true,
        opacity: 0.95,
        fog: false,
        toneMapped: false
      })

      countryLinesRef.current.geometry = lineGeometry
      countryLinesRef.current.material = lineMaterial
    } catch (e) {
      console.warn('Error rendering country borders:', e)
    }
  }, [geojsonData])

  return (
    <group>
      {/* Atmosphere glow - enhanced */}
      <mesh ref={atmosphereRef} scale={1.12}>
        <sphereGeometry args={[1, 128, 128]} />
        <meshBasicMaterial
          side={THREE.BackSide}
          transparent
          opacity={0.18}
          color="#0055dd"
        />
      </mesh>

      {/* Earth sphere - featuring real-world satellite imagery */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[1, 256, 256]} />
        <meshStandardMaterial
          map={textureRef.current}
          roughness={0.6}
          metalness={0.02}
          emissive="#001a33"
          emissiveIntensity={0.3}
        />
      </mesh>

      {/* Country borders */}
      <lineSegments ref={countryLinesRef} />

      {/* Emission hotspot markers (on globe surface) */}
      {hotspots.map((spot, i) => (
        <EmissionMarker key={i} spot={spot} />
      ))}
    </group>
  )
}

function EmissionMarker({ spot }) {
  const ref = useRef()
  const [hovered, setHovered] = useState(false)

  useFrame(({ clock }) => {
    if (ref.current) {
      // Pulse scale
      const t = clock.getElapsedTime()
      const pulse = 1 + Math.sin(t * 2 + spot.lon) * 0.3
      ref.current.scale.setScalar(pulse)
    }
  })

  // Convert lat/lon to 3D sphere coordinates
  const phi = (90 - spot.lat) * (Math.PI / 180)
  const theta = (spot.lon + 180) * (Math.PI / 180)
  const r = 1.02
  const x = -r * Math.sin(phi) * Math.cos(theta)
  const y = r * Math.cos(phi)
  const z = r * Math.sin(phi) * Math.sin(theta)

  // Color based on emission level - updated palette
  let color, emissiveIntensity
  if (spot.level === 'high') {
    // High emitter: bright red
    color = '#ff2a2a'
    emissiveIntensity = hovered ? 4 : 2.5
  } else if (spot.level === 'medium') {
    // Medium emitter: orange
    color = '#ff8c00'
    emissiveIntensity = hovered ? 3 : 1.8
  } else if (spot.level === 'low') {
    // Low emitter: yellow
    color = '#ffb300'
    emissiveIntensity = hovered ? 2.5 : 1.2
  } else if (spot.intensity > 0.5) {
    color = '#ff2a2a'
    emissiveIntensity = hovered ? 4 : 2.5
  } else if (spot.intensity > 0.15) {
    color = '#ffb300'
    emissiveIntensity = hovered ? 3 : 1.8
  } else {
    color = '#44ff88'
    emissiveIntensity = hovered ? 2.5 : 1.2
  }

  const size = 0.010 + spot.intensity * 0.025

  return (
    <mesh
      ref={ref}
      position={[x, y, z]}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
    >
      <sphereGeometry args={[size, 12, 12]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={emissiveIntensity}
        transparent
        opacity={0.95}
      />
    </mesh>
  )
}

// ── Flat 2D Map Plane ───────────────────────────────────────────────────────
function MapPlane({ hotspots = [] }) {
  const textureRef = useRef(null)

  useEffect(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 1024
    canvas.height = 512
    const ctx = canvas.getContext('2d')

    // Ocean background
    const grad = ctx.createLinearGradient(0, 0, 0, 512)
    grad.addColorStop(0, '#0a1628')
    grad.addColorStop(0.5, '#0d2040')
    grad.addColorStop(1, '#0a1628')
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, 1024, 512)

    // Continental outlines
    ctx.fillStyle = '#112240'
    // North America
    ctx.fillRect(60, 100, 160, 180)
    // South America
    ctx.fillRect(120, 280, 100, 160)
    // Europe
    ctx.fillRect(400, 80, 100, 120)
    // Africa
    ctx.fillRect(420, 180, 120, 200)
    // Asia
    ctx.fillRect(520, 60, 260, 200)
    // Australia
    ctx.fillRect(740, 300, 120, 100)

    // Lat/Lon grid
    ctx.strokeStyle = 'rgba(0, 170, 255, 0.1)'
    ctx.lineWidth = 1
    for (let i = 0; i <= 12; i++) {
      ctx.beginPath()
      ctx.moveTo(i * 85.3, 0)
      ctx.lineTo(i * 85.3, 512)
      ctx.stroke()
    }
    for (let j = 0; j <= 6; j++) {
      ctx.beginPath()
      ctx.moveTo(0, j * 85.3)
      ctx.lineTo(1024, j * 85.3)
      ctx.stroke()
    }

    // Draw hotspots
    hotspots.forEach(spot => {
      const x = ((spot.lon + 180) / 360) * 1024
      const y = ((90 - spot.lat) / 180) * 512
      const intensity = spot.intensity || 0.5
      
      // Color based on emission level - updated palette
      let color
      if (spot.level === 'high') {
        color = '#ff2a2a'  // High: bright red
      } else if (spot.level === 'medium') {
        color = '#ff8c00'  // Medium: orange
      } else if (spot.level === 'low') {
        color = '#ffb300'  // Low: yellow
      } else if (intensity > 0.5) {
        color = '#ff2a2a'
      } else if (intensity > 0.15) {
        color = '#ffb300'
      } else {
        color = '#44ff88'
      }
      
      const radius = 6 + intensity * 18

      // Glow effect
      const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius * 1.5)
      gradient.addColorStop(0, `${color}60`)
      gradient.addColorStop(1, `${color}00`)
      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.arc(x, y, radius * 1.5, 0, Math.PI * 2)
      ctx.fill()

      // Main marker
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.arc(x, y, radius * 0.5, 0, Math.PI * 2)
      ctx.fill()
    })

    textureRef.current = new THREE.CanvasTexture(canvas)
  }, [hotspots])

  return (
    <mesh position={[2.5, 0, 0]} rotation={[0, 0, 0]}>
      <planeGeometry args={[2.4, 1.2]} />
      <meshBasicMaterial map={textureRef.current} transparent />
    </mesh>
  )
}

// ── Main Globe Component ─────────────────────────────────────────────────────
export default function Globe({ hotspots = [] }) {
  const [geojsonData, setGeojsonData] = useState(null)
  const [zoomLevel, setZoomLevel] = useState(2.8)

  // Load country borders from GeoJSON
  useEffect(() => {
    fetch('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson')
      .then(res => res.json())
      .then(data => setGeojsonData(data))
      .catch(err => console.warn('Could not load GeoJSON:', err))
  }, [])

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas
        camera={{ position: [0, 0, zoomLevel], fov: 50 }}
        gl={{ antialias: true, alpha: true, precision: 'highp' }}
        style={{ background: 'transparent' }}
        dpr={[1, 2]}
      >
        {/* Lighting setup */}
        <ambientLight intensity={0.4} />
        <directionalLight
          position={[5, 3, 5]}
          intensity={1.4}
          color="#aabbff"
          castShadow
        />
        <directionalLight position={[-3, -2, -3]} intensity={0.3} color="#002244" />
        <pointLight position={[2, 2, 2]} intensity={0.6} color="#0088ff" />

        {/* Stars background - dynamic */}
        <Stars
          radius={100}
          depth={80}
          count={5000}
          factor={4}
          saturation={0.6}
          fade
          speed={0.5}
        />

        {/* Earth with country borders */}
        <EarthGlobe hotspots={hotspots} geojsonData={geojsonData} />

        {/* Real-world location labels */}
        {REAL_LOCATIONS.map((location, i) => (
          <LocationLabel key={i} location={location} zoomLevel={zoomLevel} />
        ))}

        {/* Advanced controls - click to rotate, scroll to zoom */}
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          minDistance={1.2}
          maxDistance={8}
          autoRotate={true}
          autoRotateSpeed={0.5}
          rotateSpeed={0.5}
          zoomSpeed={1.2}
          onEnd={(e) => {
            if (e?.object?.getDistance) {
              setZoomLevel(e.object.getDistance())
            }
          }}
        />
      </Canvas>
    </div>
  )
}
