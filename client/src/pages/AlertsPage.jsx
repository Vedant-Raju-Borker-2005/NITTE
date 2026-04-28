import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { formatDistanceToNow } from 'date-fns'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import useStore from '../store/useStore.js'
import { getAlerts } from '../api/client.js'

const SEV_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2 }
const SEV_COLOR = { CRITICAL: '#ff4444', HIGH: '#ff8c00', MEDIUM: '#ffb300' }

function AlertRow({ alert, index, onAcknowledge }) {
  const [expanded, setExpanded] = useState(false)
  const time = alert.timestamp ? formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true }) : 'just now'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.03 }}
      style={{
        background: 'rgba(13,21,37,0.7)', border: `1px solid ${SEV_COLOR[alert.severity] || '#445577'}25`,
        borderLeft: `3px solid ${SEV_COLOR[alert.severity] || '#445577'}`, borderRadius: 8, marginBottom: 8,
        overflow: 'hidden', cursor: 'pointer', opacity: alert.acknowledged ? 0.6 : 1
      }}
    >
      <div style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 14px' }} onClick={() => setExpanded(!expanded)}>
        <div style={{ width: 36, height: 36, borderRadius: 8, flexShrink: 0, background: `${SEV_COLOR[alert.severity] || '#445577'}15`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>
          {alert.severity === 'CRITICAL' ? '🔴' : alert.severity === 'HIGH' ? '🟠' : '🟡'}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:3 }}>
            <span className={`badge badge-${alert.severity?.toLowerCase()}`}>{alert.severity}</span>
            {!alert.acknowledged && <span style={{ fontSize:9, fontWeight:700, color:'var(--neon-blue)', background:'rgba(0,170,255,0.1)', padding:'1px 5px', borderRadius:3 }}>NEW</span>}
            {alert.acknowledged && <span style={{ fontSize:9, fontWeight:700, color:'var(--text-muted)', border: '1px solid var(--border)', padding:'1px 5px', borderRadius:3 }}>ACKNOWLEDGED</span>}
          </div>
          <div style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{alert.facility_name}</div>
          <div style={{ fontSize:10, color:'var(--text-secondary)' }}>{alert.country} · {time}</div>
        </div>

        <div style={{ textAlign:'right', flexShrink:0 }}>
          <div style={{ fontFamily:'var(--font-mono)', fontSize:16, fontWeight:700, color: SEV_COLOR[alert.severity] || '#ffb300' }}>
            {Number(alert.emission_rate_kg_hr || 0).toFixed(0)}
          </div>
          <div style={{ fontSize:9, color:'var(--text-muted)' }}>kg/hr</div>
        </div>

        <div style={{ color:'var(--text-muted)', fontSize:12, flexShrink:0 }}>{expanded ? '▲' : '▼'}</div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height:0, opacity:0 }} animate={{ height:'auto', opacity:1 }} exit={{ height:0, opacity:0 }} transition={{ duration:0.2 }} style={{ overflow:'hidden' }}>
            <div style={{ padding:'0 14px 12px', borderTop:'1px solid rgba(68,85,119,0.2)' }}>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:12, paddingTop:12, paddingBottom: 12 }}>
                {[
                  { label:'Facility ID', value: alert.facility_id },
                  { label:'Type', value: alert.facility_type?.replace('_',' ') || '—' },
                  { label:'Operator', value: alert.operator || '—' },
                  { label:'Coordinates', value: alert.lat && alert.lon ? `${alert.lat?.toFixed(2)}, ${alert.lon?.toFixed(2)}` : '—' },
                  { label:'Timestamp', value: alert.timestamp ? new Date(alert.timestamp).toLocaleString() : '—' },
                  { label:'Status', value: alert.acknowledged ? 'Acknowledged' : 'Unacknowledged' },
                ].map(f => (
                  <div key={f.label}>
                    <div style={{ fontSize:9, color:'var(--text-muted)', letterSpacing:'0.1em', marginBottom:2 }}>{f.label.toUpperCase()}</div>
                    <div style={{ fontSize:11, color:'var(--text-primary)', fontFamily:'var(--font-mono)' }}>{f.value}</div>
                  </div>
                ))}
              </div>
              {!alert.acknowledged && (
                <button 
                  className="btn btn-ghost" 
                  onClick={(e) => { e.stopPropagation(); onAcknowledge(alert.id); }}
                  style={{ fontSize: 11, padding: '6px 12px', width: '100%', justifyContent: 'center' }}
                >
                  Acknowledge Alert ✓
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default function AlertsPage() {
  const queryClient = useQueryClient()
  const liveAlerts = useStore(s => s.liveAlerts) // Keep websocket/live ones if they ever exist
  const alertFilter = useStore(s => s.alertFilter)
  const setAlertFilter = useStore(s => s.setAlertFilter)

  // Request Notification permission
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  // React Query with 30s polling
  const { data, isFetching } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => getAlerts({ limit: 100 }),
    refetchInterval: 30000,
    onSuccess: (newData) => {
      // Check for new CRITICAL alerts to notify
      const currentAlerts = queryClient.getQueryData(['alerts'])?.alerts || []
      const currentIds = new Set(currentAlerts.map(a => a.id))
      const newCriticals = newData.alerts.filter(a => a.severity === 'CRITICAL' && !currentIds.has(a.id))
      
      if (newCriticals.length > 0 && 'Notification' in window && Notification.permission === 'granted') {
        new Notification('MethaneX Alert', {
          body: `${newCriticals.length} new CRITICAL emission(s) detected.`,
          icon: '/vite.svg'
        })
      }
    }
  })

  const fetchedAlerts = data?.alerts || []

  // Optimistic UI for acknowledging
  const acknowledgeMutation = useMutation({
    mutationFn: async (id) => {
      // Mock API call to ack
      return new Promise(resolve => setTimeout(() => resolve(id), 300))
    },
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['alerts'] })
      const previousData = queryClient.getQueryData(['alerts'])
      queryClient.setQueryData(['alerts'], old => ({
        ...old,
        alerts: old.alerts.map(a => a.id === id ? { ...a, acknowledged: true } : a)
      }))
      toast.success('Alert acknowledged')
      return { previousData }
    },
    onError: (err, id, context) => {
      queryClient.setQueryData(['alerts'], context.previousData)
      toast.error('Failed to acknowledge')
    }
  })

  // Merge live + fetched
  const allAlerts = [...liveAlerts, ...fetchedAlerts]
    .filter((a, i, arr) => arr.findIndex(x => x.id === a.id) === i)
    .filter(a => !alertFilter || a.severity === alertFilter)
    .sort((a, b) => (SEV_ORDER[a.severity] || 9) - (SEV_ORDER[b.severity] || 9))

  const counts = {
    CRITICAL: allAlerts.filter(a => a.severity === 'CRITICAL').length,
    HIGH: allAlerts.filter(a => a.severity === 'HIGH').length,
    MEDIUM: allAlerts.filter(a => a.severity === 'MEDIUM').length,
  }

  const exportCsv = () => {
    if (allAlerts.length === 0) return
    const csvRows = ['id,severity,facility_id,facility_name,operator,country,lat,lon,emission_rate_kg_hr,timestamp,acknowledged']
    allAlerts.forEach(a => {
      csvRows.push(`${a.id},${a.severity},${a.facility_id},"${a.facility_name}","${a.operator}",${a.country},${a.lat},${a.lon},${a.emission_rate_kg_hr},${a.timestamp},${a.acknowledged}`)
    })
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `MethaneX_Alerts_Export_${new Date().toISOString().split('T')[0]}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', overflow:'hidden', padding:24 }}>
      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', gap:16, marginBottom:20, flexShrink:0 }}>
        <div>
          <h1 style={{ fontSize:22, fontWeight:800, color:'var(--text-primary)' }}>🚨 Super-Emitter Alerts</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: 4 }}>
            <span style={{ fontSize:12, color:'var(--text-secondary)' }}>Facilities emitting above 100 kg/hr</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'rgba(0,170,255,0.1)', padding: '2px 6px', borderRadius: '4px', border: '1px solid rgba(0,170,255,0.2)' }}>
              <div className={isFetching ? "pulse-ring" : ""} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--neon-blue)', position: 'relative' }} />
              <span style={{ fontSize: 10, color: 'var(--neon-blue)', fontWeight: 600 }}>Polling Active</span>
            </div>
          </div>
        </div>

        {/* Summary badges */}
        <div style={{ display:'flex', gap:8, marginLeft:'auto' }}>
          {Object.entries(counts).map(([sev, n]) => (
            <div key={sev} style={{ background:`${SEV_COLOR[sev]}15`, border:`1px solid ${SEV_COLOR[sev]}30`, borderRadius:8, padding:'8px 14px', textAlign:'center' }}>
              <div style={{ fontFamily:'var(--font-mono)', fontSize:20, fontWeight:800, color:SEV_COLOR[sev] }}>{n}</div>
              <div style={{ fontSize:9, color:'var(--text-secondary)', fontWeight:600 }}>{sev}</div>
            </div>
          ))}
        </div>

        <button className="btn btn-ghost" onClick={exportCsv} style={{ flexShrink:0, fontSize: 12 }}>
          📥 Export CSV
        </button>
      </div>

      {/* Filter bar */}
      <div style={{ display:'flex', gap:6, marginBottom:16, flexShrink:0 }}>
        {[null, 'CRITICAL', 'HIGH', 'MEDIUM'].map(f => (
          <button key={f || 'ALL'} className={`btn ${alertFilter === f ? 'btn-primary' : 'btn-ghost'}`} style={{ padding:'5px 12px', fontSize:10 }} onClick={() => setAlertFilter(f)}>
            {f || 'ALL'} {f ? `(${allAlerts.filter(a => a.severity === f).length})` : `(${allAlerts.length})`}
          </button>
        ))}
      </div>

      {/* Alert list */}
      <div style={{ flex:1, overflow:'auto' }}>
        {allAlerts.length === 0 ? (
          <div style={{ textAlign:'center', color:'var(--text-muted)', padding:'60px 0', fontSize:14 }}>No alerts for selected severity filter</div>
        ) : (
          allAlerts.map((alert, i) => <AlertRow key={alert.id || i} alert={alert} index={i} onAcknowledge={(id) => acknowledgeMutation.mutate(id)} />)
        )}
      </div>
    </div>
  )
}
