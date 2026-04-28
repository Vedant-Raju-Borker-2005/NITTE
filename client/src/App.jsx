import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Dashboard from './components/Dashboard/Dashboard.jsx'
import useStore from './store/useStore.js'
import {
  getFacilities, getTopPolluters, getAlerts, getHeatmap,
} from './api/client.js'
import usePollScheduled from './hooks/usePollScheduled.js'


function PollingManager() {
  const { setAlerts, setConnectionStatus, setLastPollTime, resetCriticalBanner } = useStore()

  const { status } = usePollScheduled(async (results) => {
    // Convert scheduled scan results to alerts
    const alerts = results.map((r, idx) => {
      const emission = r.emission_kghr || 0
      const sev = emission >= 800 ? 'CRITICAL' : emission >= 400 ? 'HIGH' : 'MEDIUM'
      return {
        id: `${r.plant_id}-poll-${idx}`,
        severity: sev,
        facility_id: r.plant_id,
        facility_name: r.plant_name || 'Unknown',
        facility_type: 'industrial',
        operator: 'MethaneX Monitor',
        country: 'Unknown',
        lat: null, lon: null,
        emission_rate_kg_hr: emission,
        timestamp: new Date().toISOString(),
        acknowledged: false,
      }
    })
    setAlerts(alerts)
    setLastPollTime(new Date())
    setConnectionStatus('polling')
    if (alerts.some(a => a.severity === 'CRITICAL')) {
      resetCriticalBanner()
    }
  }, 30000)

  useEffect(() => {
    setConnectionStatus(status)
  }, [status])

  return null
}

export default function App() {
  const { setFacilities, setTopPolluters, setAlerts, setHeatmapData } = useStore()

  useEffect(() => {
    getFacilities().then(d => setFacilities(d.facilities)).catch(console.warn)
    getTopPolluters(15).then(d => setTopPolluters(d.top_polluters)).catch(console.warn)
    getAlerts().then(d => setAlerts(d.alerts)).catch(console.warn)
    getHeatmap().then(d => setHeatmapData(d)).catch(console.warn)
  }, [])

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'rgba(13, 21, 37, 0.95)',
            color: '#e8f0fe',
            border: '1px solid rgba(0, 170, 255, 0.3)',
            fontFamily: 'Inter, sans-serif',
            fontSize: '13px',
          },
          duration: 4000,
        }}
      />
      <PollingManager />
      <Routes>
        <Route path="/*" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  )
}
