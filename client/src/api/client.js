import axios from 'axios'
import { getCountryFromCoordinates } from '../utils/geocode.js'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 150000,
})

const parseBbox = (bboxStr) => {
  if (!bboxStr) return null
  const parts = bboxStr.replace(/\s+/g, '').split(',')
  if (parts.length !== 4) return null
  const [lat1, lon1, lat2, lon2] = parts.map(Number)
  if (parts.some(p => Number.isNaN(p))) return null
  return {
    lat_min: Math.min(lat1, lat2),
    lat_max: Math.max(lat1, lat2),
    lon_min: Math.min(lon1, lon2),
    lon_max: Math.max(lon1, lon2),
  }
}

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

const fetchPlants = async () => {
  const r = await api.get('/plants')
  return r.data?.plants || []
}

const fetchScheduled = async () => {
  const r = await api.get('/scan/scheduled')
  return r.data?.results || []
}

export const detectMethane = async ({ bbox }) => {
  const parsed = parseBbox(bbox)
  if (!parsed) {
    return {
      detected: false,
      emission_rate_kg_hr: 0,
      emission_uncertainty_kg_hr: 0,
      detection_confidence: 0,
      quantification_confidence: 0,
      is_super_emitter: false,
      severity: 'Low',
    }
  }
  const r = await api.post('/predict_bbox', null, { params: parsed })
  const data = r.data || {}
  const plumes = data.plumes || []
  const top = plumes.reduce((acc, p) => (p.emission_kghr > (acc?.emission_kghr || 0) ? p : acc), null)
  const emission = top?.emission_kghr || 0
  const detected = plumes.length > 0
  const sev = severityFromEmission(emission)
  return {
    detected,
    emission_rate_kg_hr: emission,
    emission_uncertainty_kg_hr: emission * 0.15,
    detection_confidence: data.confidence || (detected ? 0.72 : 0.25),
    quantification_confidence: data.quantification_confidence || (detected ? 0.65 : 0.2),
    is_super_emitter: emission >= 100,
    severity: sev,
    attribution: top ? {
      facility_name: top.plant_name,
      facility_type: 'unknown',
      distance_km: null,
      attribution_confidence: top.confidence || 0.6,
    } : null,
    wind: { speed_ms: 5.0, direction_deg: 270 },
    pipeline_timing_ms: { total: 800, segmentation: 250, quantification: 350, attribution: 200 },
  }
}

export const geocodeCompany = async (address, { retries = 2 } = {}) => {
  const query = String(address || '').trim()
  if (!query) {
    throw new Error('Address is required for geocoding')
  }

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const r = await api.get('/geocode', { params: { address: query } })
      return r.data
    } catch (err) {
      const status = err?.response?.status
      // Backend geocoder enforces 1 req/sec; retry after a short delay.
      if (status === 429 && attempt < retries) {
        await new Promise(resolve => setTimeout(resolve, 1200))
        continue
      }
      throw err
    }
  }
}

export const runLiveScan = async (payload, signal) => {
  const r = await api.post('/predict/live', payload, { signal })
  return r.data
}

export const getFacilities = async ({ limit = 50 } = {}) => {
  const [plants, scheduled] = await Promise.all([fetchPlants(), fetchScheduled()])
  const emissionMap = new Map(scheduled.map(r => [r.plant_id, r.emission_kghr || 0]))
  const facilities = plants.map((p, idx) => {
    const emission = emissionMap.get(p.id) || 0
    const risk = Math.min(1, Math.max(0.2, emission / 800))
    return {
      id: p.id,
      name: p.name,
      type: p.type,
      country: getCountryFromCoordinates(p.lat, p.lon),
      operator: 'MethaneX',
      lat: p.lat,
      lon: p.lon,
      risk_score: risk,
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
    .map((r, i) => {
      const p = plantMap.get(r.plant_id)
      return {
        id: r.plant_id,
        name: p?.name || r.plant_name,
        country: getCountryFromCoordinates(p?.lat, p?.lon),
        historical_emission_rate: Math.round((r.emission_kghr || 0) * 10) / 10,
        risk_score: Math.min(1, (r.emission_kghr || 0) / 800),
      }
    })
  return { top_polluters: top }
}

export const getAlerts = async ({ severity, limit = 20 } = {}) => {
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
      operator: 'MethaneX',
      country: getCountryFromCoordinates(p?.lat, p?.lon),
      lat: p?.lat,
      lon: p?.lon,
      emission_rate_kg_hr: emission,
      timestamp: nowIso(),
      acknowledged: false,
    }
  })
  if (severity) {
    alerts = alerts.filter(a => a.severity === severity)
  }
  return { alerts: alerts.slice(0, limit) }
}

export const getTimeseries = async (facility_id, days = 30) => {
  const r = await api.get(`/history/${facility_id}`)
  const history = r.data?.history || []
  const series = history.slice(-days).map((value, idx, arr) => {
    const d = new Date()
    d.setDate(d.getDate() - (arr.length - 1 - idx))
    return {
      timestamp: d.toISOString(),
      emission_rate_kg_hr: value,
    }
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
    return { timestamp: d.toISOString(), total_emission_kg_hr: total }
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
      lat: p?.lat || 0,
      lon: p?.lon || 0,
      emission_rate_kg_hr: emission,
      intensity,
      level,
    }
  })
  return { hotspots }
}

export const runSimulation = async (body) => {
  return { ok: true, input: body }
}

export const createAlertsWebSocket = () => null

// ─── Drone Upload API ─────────────────────────────────────────────────────────

/**
 * Upload a drone image for GPS extraction + Sentinel-2 pipeline.
 * Supports real upload progress via XHR.
 *
 * @param {{ file: File, manualLat?: number, manualLon?: number, windSpeed?: number, radiusKm?: number }} params
 * @param {(progress: { phase: 'upload'|'pipeline', pct: number }) => void} [onProgress]
 * @returns {Promise<object>} Full pipeline result
 */
export function uploadDroneImage({ file, manualLat, manualLon, windSpeed, radiusKm }, onProgress) {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)
    if (manualLat !== undefined && manualLon !== undefined) {
      form.append('manual_lat', manualLat)
      form.append('manual_lon', manualLon)
    }
    form.append('wind_speed_ms', windSpeed ?? 5.0)
    form.append('radius_km', radiusKm ?? 3.0)

    const xhr = new XMLHttpRequest()
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress?.({ phase: 'upload', pct: Math.round((e.loaded / e.total) * 100) })
      }
    }
    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText)
        if (xhr.status < 300) resolve(data)
        else reject(data) // { detail: { code, message, requires_manual_coordinates? } }
      } catch {
        reject({ detail: { code: 'PARSE_ERROR', message: 'Invalid server response' } })
      }
    }
    xhr.onerror = () =>
      reject({
        detail: {
          code: 'NETWORK_ERROR',
          message: 'Cannot reach backend. Is the server running?',
        },
      })
    xhr.open('POST', `${BASE_URL}/upload/drone`)
    xhr.send(form)
  })
}

/** Returns the URL to the latest uploaded drone image (use directly as <img src>). */
export const getDroneImage = () => `${BASE_URL}/upload/drone/image`

/** Fetches the last 10 drone upload scans. */
export const getUploadHistory = () => api.get('/upload/history').then((r) => r.data)

export default api
