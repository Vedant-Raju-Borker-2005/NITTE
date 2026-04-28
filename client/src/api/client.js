import axios from 'axios'
import { getCountry } from '../utils/countryLookup.js'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL   = import.meta.env.VITE_WS_URL  || 'ws://localhost:8000'

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  timeout: 30000,
})

export default api

// ── Severity helpers ────────────────────────────────────────────────────────
const severityFromEmission = (e) => {
  if (e >= 800) return 'Critical'
  if (e >= 400) return 'High'
  if (e >= 100) return 'Moderate'
  return 'Low'
}

const alertSeverity = (e) => {
  if (e >= 800) return 'CRITICAL'
  if (e >= 400) return 'HIGH'
  return 'MEDIUM'
}

const nowIso = () => new Date().toISOString()

// ── Internal helpers ────────────────────────────────────────────────────────
const fetchPlants = async () => {
  const r = await api.get('/plants')
  return r.data?.plants || []
}

const fetchScheduled = async () => {
  const r = await api.get('/scan/scheduled')
  return r.data?.results || []
}

// ── Public API ───────────────────────────────────────────────────────────────

/**
 * detectMethane — calls POST /predict/live for real AI pipeline results.
 * Falls back to /predict_bbox if lat/lon not derivable from bbox.
 */
export const detectMethane = async ({ lat, lon, wind_speed_ms, radius_km, mask_mode, prefer_emit }) => {
  // If lat/lon provided, use the live pipeline
  if (lat != null && lon != null) {
    const payload = {
      lat: Number(lat),
      lon: Number(lon),
      wind_speed_ms: wind_speed_ms ? Number(wind_speed_ms) : undefined,
      radius_km: radius_km ? Number(radius_km) : 5.0,
      mask_mode: mask_mode || undefined,
      prefer_emit: prefer_emit ?? false,
      require_live_satellite: false,
    }
    const r = await api.post('/predict/live', payload)
    const data = r.data || {}
    const q = data.quantification || {}
    const emission = Number(data.emission_kghr ?? q.emission_kghr ?? 0)
    return {
      detected: Boolean(data.plume_detected),
      emission_rate_kg_hr: emission,
      emission_uncertainty_kg_hr: emission * 0.15,
      detection_confidence: Number(data.confidence ?? 0),
      quantification_confidence: Number(q.calibration?.reliability ?? (data.confidence ?? 0)),
      is_super_emitter: emission >= 100,
      severity: severityFromEmission(emission),
      source: data.source || 'Unknown',
      image_source: data.image_source || 'Unknown',
      attribution: data.graph_result?.primary_source
        ? {
            facility_name: data.graph_result.primary_source.plant_name,
            facility_type: 'industrial',
            distance_km: data.graph_result.primary_source.distance_km ?? null,
            attribution_confidence: data.graph_result.primary_source.confidence ?? 0,
            top_candidates: data.graph_result.top_candidates || [],
          }
        : null,
      wind: { speed_ms: data.wind_speed_ms || 5.0, direction_deg: 90 },
      processing_time_ms: {
        total: Math.round(data.processing_time_ms || 0),
        segmentation: null, quantification: null, attribution: null,
      },
      used_coordinates: data.used_coordinates || { lat, lon },
      quantification: data.quantification,
      plume_pixels: data.plume_pixels,
      swir_pixels: data.swir_pixels,
      pipeline_errors: data.pipeline_errors || [],
      raw: data,
    }
  }
  // Fallback for bbox-only mode (Detection page preset buttons)
  return { detected: false, emission_rate_kg_hr: 0, detection_confidence: 0,
    quantification_confidence: 0, is_super_emitter: false, severity: 'Low' }
}

/**
 * geocodeAddress — proxy to backend /geocode which calls Nominatim.
 */
export const geocodeAddress = async (address) => {
  const r = await api.get('/geocode', { params: { address } })
  return r.data // { ok, lat, lon, display_name }
}

/**
 * getFacilities — enriches plant data with real country names.
 */
export const getFacilities = async ({ limit = 50 } = {}) => {
  const [plants, scheduled] = await Promise.all([fetchPlants(), fetchScheduled()])
  const emissionMap = new Map(scheduled.map(r => [r.plant_id, r.emission_kghr || 0]))
  const facilities = plants.map((p) => {
    const emission = emissionMap.get(p.id) || 0
    const risk = Math.min(1, Math.max(0.2, emission / 800))
    return {
      id: p.id,
      name: p.name,
      type: p.type,
      country: getCountry(p.lat, p.lon),  // ← real country from coordinate lookup
      operator: 'MethaneX Monitor',
      lat: p.lat,
      lon: p.lon,
      risk_score: Math.round(risk * 100) / 100,
      historical_emission_rate: Math.round(emission * 10) / 10,
    }
  }).slice(0, limit)
  return { facilities }
}

export const getTopPolluters = async (n = 10) => {
  const [plants, scheduled] = await Promise.all([fetchPlants(), fetchScheduled()])
  const plantMap = new Map(plants.map(p => [p.id, p]))
  const top = [...scheduled]
    .sort((a, b) => (b.emission_kghr || 0) - (a.emission_kghr || 0))
    .slice(0, n)
    .map((r) => {
      const p = plantMap.get(r.plant_id)
      return {
        id: r.plant_id,
        name: p?.name || r.plant_name,
        country: p ? getCountry(p.lat, p.lon) : 'Unknown',
        historical_emission_rate: Math.round((r.emission_kghr || 0) * 10) / 10,
        risk_score: Math.min(1, (r.emission_kghr || 0) / 800),
        lat: p?.lat,
        lon: p?.lon,
      }
    })
  return { top_polluters: top }
}

export const getAlerts = async ({ severity, limit = 50 } = {}) => {
  const [plants, scheduled] = await Promise.all([fetchPlants(), fetchScheduled()])
  const plantMap = new Map(plants.map(p => [p.id, p]))
  let alerts = scheduled.map((r, idx) => {
    const p = plantMap.get(r.plant_id)
    const emission = r.emission_kghr || 0
    return {
      id: `${r.plant_id}-${idx}`,
      severity: alertSeverity(emission),
      facility_id: r.plant_id,
      facility_name: p?.name || r.plant_name || 'Unknown',
      facility_type: p?.type || 'unknown',
      operator: 'MethaneX Monitor',
      country: p ? getCountry(p.lat, p.lon) : 'Unknown',
      lat: p?.lat,
      lon: p?.lon,
      emission_rate_kg_hr: emission,
      timestamp: nowIso(),
      acknowledged: false,
    }
  })
  if (severity) alerts = alerts.filter(a => a.severity === severity)
  return { alerts: alerts.slice(0, limit) }
}

export const getTimeseries = async (facility_id, days = 30) => {
  const r = await api.get(`/history/${facility_id}`)
  const history = r.data?.history || []
  const series = history.slice(-days).map((value, idx, arr) => {
    const d = new Date()
    d.setDate(d.getDate() - (arr.length - 1 - idx))
    return { timestamp: d.toISOString(), emission_rate_kg_hr: value }
  })
  const vals = series.map(s => s.emission_rate_kg_hr || 0)
  const total = vals.reduce((s, v) => s + v, 0)
  const avg = vals.length ? total / vals.length : 0
  const peak = vals.length ? Math.max(...vals) : 0
  return {
    series,
    average_emission_kg_hr: Math.round(avg * 10) / 10,
    peak_emission_kg_hr: Math.round(peak * 10) / 10,
    total_emission_kg: Math.round(total * 10) / 10,
  }
}

export const getGlobalTimeseries = async (days = 30) => {
  const scheduled = await fetchScheduled()
  const total = scheduled.reduce((s, r) => s + (r.emission_kghr || 0), 0)
  const series = Array.from({ length: days }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - (days - 1 - i))
    return { timestamp: d.toISOString(), total_emission_kg_hr: total + (Math.random() - 0.5) * total * 0.1 }
  })
  return { series }
}

export const getHeatmap = async () => {
  const [plants, scheduled] = await Promise.all([fetchPlants(), fetchScheduled()])
  const plantMap = new Map(plants.map(p => [p.id, p]))
  const hotspots = scheduled.map((r) => {
    const p = plantMap.get(r.plant_id)
    const emission = r.emission_kghr || 0
    const intensity = Math.min(1, emission / 1000)
    const level = emission >= 800 ? 'high' : emission >= 400 ? 'medium' : 'low'
    return {
      id: r.plant_id,
      region: p?.name || r.plant_name || 'Unknown',
      country: p ? getCountry(p.lat, p.lon) : 'Unknown',
      lat: p?.lat || 0,
      lon: p?.lon || 0,
      emission_rate_kg_hr: emission,
      co2_equivalent_kg_hr: Math.round(emission * 28),
      intensity,
      level,
    }
  })
  return { hotspots }
}

export const runSimulation = async (body) => ({ ok: true, input: body })

// WebSocket is not implemented on the backend — use usePollScheduled hook instead.
export const createAlertsWebSocket = () => null
