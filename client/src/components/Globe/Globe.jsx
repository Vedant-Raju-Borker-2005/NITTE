import { useRef, useEffect, useState, useMemo } from 'react'
import { Canvas, useFrame, useThree, extend } from '@react-three/fiber'
import { OrbitControls, Stars, Html, useTexture } from '@react-three/drei'
import * as THREE from 'three'
import useStore from '../../store/useStore.js'

// ── Atmosphere shader (Fresnel glow) ────────────────────────────────────────
const AtmosphereVert = /* glsl */`
  varying vec3 vNormal;
  varying vec3 vPosition;
  void main() {
    vNormal   = normalize(normalMatrix * normal);
    vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`
const AtmosphereFrag = /* glsl */`
  uniform vec3  glowColor;
  uniform float coeff;
  uniform float power;
  varying vec3 vNormal;
  varying vec3 vPosition;
  void main() {
    float intensity = pow(coeff - dot(normalize(vNormal), normalize(-vPosition)), power);
    gl_FragColor = vec4(glowColor, intensity);
  }
`

function Atmosphere() {
  const meshRef = useRef()
  const mat = useMemo(() => new THREE.ShaderMaterial({
    vertexShader:   AtmosphereVert,
    fragmentShader: AtmosphereFrag,
    uniforms: {
      glowColor: { value: new THREE.Color('#3ea6ff') },
      coeff:     { value: 0.65 },
      power:     { value: 4.5 },
    },
    side: THREE.FrontSide,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
  }), [])

  return (
    <mesh ref={meshRef} scale={1.14}>
      <sphereGeometry args={[1, 64, 64]} />
      <primitive object={mat} attach="material" />
    </mesh>
  )
}

// ── Earth sphere ─────────────────────────────────────────────────────────────
function EarthGlobe({ hotspots = [], geojsonData = null }) {
  const meshRef       = useRef()
  const cloudsRef     = useRef()
  const countryRef    = useRef()
  const { gl }        = useThree()

  // Texture URLs — CORS-friendly CDN sources
  const EARTH_DAY   = 'https://raw.githubusercontent.com/turban/webgl-earth/master/images/2_no_clouds_4k.jpg'
  const EARTH_SPEC  = 'https://raw.githubusercontent.com/turban/webgl-earth/master/images/water_4k.png'
  const EARTH_BUMP  = 'https://raw.githubusercontent.com/turban/webgl-earth/master/images/elev_bump_4k.jpg'
  const CLOUDS_IMG  = 'https://raw.githubusercontent.com/turban/webgl-earth/master/images/fair_clouds_4k.png'

  const [textures, setTextures] = useState({})

  useEffect(() => {
    const loader = new THREE.TextureLoader()
    loader.setCrossOrigin('anonymous')
    const load = (url) => new Promise((res, rej) => loader.load(url, res, undefined, rej))

    Promise.allSettled([
      load(EARTH_DAY),
      load(EARTH_SPEC),
      load(EARTH_BUMP),
      load(CLOUDS_IMG),
    ]).then(([day, spec, bump, clouds]) => {
      setTextures({
        day:    day.status    === 'fulfilled' ? day.value    : null,
        spec:   spec.status   === 'fulfilled' ? spec.value   : null,
        bump:   bump.status   === 'fulfilled' ? bump.value   : null,
        clouds: clouds.status === 'fulfilled' ? clouds.value : null,
      })
    })
  }, [])

  // Globe is stationary — no auto-rotation
  // Only clouds drift slowly to add life without spinning the globe
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (cloudsRef.current) cloudsRef.current.rotation.y = t * 0.006
  })

  // GeoJSON country border lines
  useEffect(() => {
    if (!geojsonData || !countryRef.current) return
    const positions = []

    const addRing = (ring) => {
      for (let i = 0; i < ring.length - 1; i++) {
        for (let k = 0; k < 2; k++) {
          const [lon, lat] = ring[i + k]
          const phi   = (90 - lat) * (Math.PI / 180)
          const theta = (lon + 180) * (Math.PI / 180)
          const r     = 1.002
          positions.push(
            -r * Math.sin(phi) * Math.cos(theta),
             r * Math.cos(phi),
             r * Math.sin(phi) * Math.sin(theta)
          )
        }
      }
    }

    try {
      geojsonData.features.forEach(f => {
        const { type, coordinates } = f.geometry
        if (type === 'Polygon')      coordinates.forEach(addRing)
        else if (type === 'MultiPolygon') coordinates.forEach(poly => poly.forEach(addRing))
      })
    } catch (e) { /* ignore bad GeoJSON */ }

    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3))
    const mat = new THREE.LineBasicMaterial({
      color: 0x88ccff, linewidth: 1,
      transparent: true, opacity: 0.45,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })
    countryRef.current.geometry = geo
    countryRef.current.material = mat
  }, [geojsonData])

  const hasDay = !!textures.day

  return (
    <group>
      {/* Earth sphere — stationary */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[1, 128, 128]} />
        {hasDay ? (
          <meshPhongMaterial
            map={textures.day}
            specularMap={textures.spec || undefined}
            bumpMap={textures.bump || undefined}
            bumpScale={0.04}
            specular={new THREE.Color('#225577')}
            shininess={18}
          />
        ) : (
          <meshPhongMaterial color="#0d3b6e" specular="#335577" shininess={10} />
        )}
      </mesh>

      {/* Clouds — drift slowly */}
      {textures.clouds && (
        <mesh ref={cloudsRef} scale={1.005}>
          <sphereGeometry args={[1, 64, 64]} />
          <meshPhongMaterial
            map={textures.clouds}
            transparent
            opacity={0.30}
            depthWrite={false}
            blending={THREE.NormalBlending}
          />
        </mesh>
      )}

      {/* Country border line segments */}
      <lineSegments ref={countryRef} />

      {/* Atmosphere Fresnel glow */}
      <Atmosphere />

      {/* Emission hotspot markers — stationary at lat/lon positions */}
      {hotspots.map((spot, i) => (
        <EmissionMarker key={i} spot={spot} />
      ))}
    </group>
  )
}

// ── Emission Marker ──────────────────────────────────────────────────────────
function EmissionMarker({ spot }) {
  const ref     = useRef()
  const ringRef = useRef()
  const [hovered, setHovered] = useState(false)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (ref.current) {
      const pulse = 1 + Math.sin(t * 3 + spot.lon * 0.1) * 0.25
      ref.current.scale.setScalar(pulse)
    }
    if (ringRef.current) {
      const expand = 1 + ((t * 1.5 + spot.lat) % 1) * 1.5
      ringRef.current.scale.setScalar(expand)
      ringRef.current.material.opacity = Math.max(0, 0.6 - ((t * 1.5 + spot.lat) % 1) * 0.7)
    }
  })

  const phi   = (90 - spot.lat) * (Math.PI / 180)
  const theta = (spot.lon + 180) * (Math.PI / 180)
  const r     = 1.018
  const pos   = [
    -r * Math.sin(phi) * Math.cos(theta),
     r * Math.cos(phi),
     r * Math.sin(phi) * Math.sin(theta),
  ]

  let color = '#44ff88'
  let emInt = 1.2
  if (spot.level === 'high' || spot.intensity > 0.5) {
    color = '#ff2a2a'; emInt = hovered ? 5 : 3
  } else if (spot.level === 'medium' || spot.intensity > 0.15) {
    color = '#ff8c00'; emInt = hovered ? 4 : 2
  } else if (spot.level === 'low') {
    color = '#ffcc00'; emInt = hovered ? 3 : 1.5
  }

  const size = 0.008 + (spot.intensity || 0.3) * 0.018

  return (
    <group position={pos} onPointerOver={() => setHovered(true)} onPointerOut={() => setHovered(false)}>
      {/* Core dot */}
      <mesh ref={ref}>
        <sphereGeometry args={[size, 12, 12]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={emInt} transparent opacity={0.95} />
      </mesh>
      {/* Ripple ring */}
      <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[size * 1.2, size * 1.8, 32]} />
        <meshBasicMaterial color={color} transparent opacity={0.5} side={THREE.DoubleSide} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>
    </group>
  )
}

// ── Main Globe export ────────────────────────────────────────────────────────
export default function Globe({ hotspots = [] }) {
  const [geojsonData, setGeojsonData] = useState(null)

  useEffect(() => {
    fetch('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson')
      .then(r => r.json())
      .then(setGeojsonData)
      .catch(() => {})
  }, [])

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: 'radial-gradient(ellipse at center, #0d1b2a 0%, #020408 70%)' }}>
      <Canvas
        camera={{ position: [0, 0, 2.6], fov: 48 }}
        gl={{ antialias: true, alpha: false, precision: 'highp', toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.1 }}
        dpr={[1, 2]}
      >
        {/* Deep-space background stars */}
        <Stars radius={300} depth={120} count={8000} factor={5} saturation={0.4} fade speed={0.3} />

        {/* Sun-like key light */}
        <directionalLight position={[5, 2, 5]} intensity={2.2} color="#fff8ee" />
        {/* Subtle fill from opposite side */}
        <directionalLight position={[-4, -1, -4]} intensity={0.08} color="#1a2a4a" />
        {/* Dim ambient so dark side isn't pitch black */}
        <ambientLight intensity={0.06} />

        <EarthGlobe hotspots={hotspots} geojsonData={geojsonData} />

        <OrbitControls
          enablePan={false}
          enableZoom={true}
          minDistance={1.3}
          maxDistance={6}
          autoRotate={false}
          rotateSpeed={0.4}
          zoomSpeed={1.0}
          enableDamping
          dampingFactor={0.07}
        />
      </Canvas>

      {/* Overlay legend */}
      <div style={{
        position: 'absolute', bottom: 16, left: 16,
        display: 'flex', flexDirection: 'column', gap: 6,
        fontSize: 11, color: 'rgba(180,210,255,0.7)',
        pointerEvents: 'none', userSelect: 'none',
      }}>
        {hotspots.length > 0 && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff2a2a', display: 'inline-block', boxShadow: '0 0 6px #ff2a2a' }} />
              High emission
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff8c00', display: 'inline-block', boxShadow: '0 0 6px #ff8c00' }} />
              Medium emission
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#44ff88', display: 'inline-block', boxShadow: '0 0 6px #44ff88' }} />
              Low / normal
            </div>
          </>
        )}
        <div style={{ marginTop: 4, opacity: 0.5 }}>Drag to rotate · Scroll to zoom</div>
      </div>
    </div>
  )
}
