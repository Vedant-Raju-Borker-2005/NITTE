import { motion, AnimatePresence } from 'framer-motion'
import { formatDistanceToNow } from 'date-fns'
import useStore from '../../store/useStore.js'

function severityClass(s) {
  if (s === 'CRITICAL') return 'badge-critical'
  if (s === 'HIGH') return 'badge-high'
  if (s === 'MEDIUM') return 'badge-medium'
}

function severityColor(s) {
  if (s === 'CRITICAL') return '#ff4444'
  if (s === 'HIGH') return '#ff8c00'
  if (s === 'MEDIUM') return '#ffb300'
}

function AlertItem({ alert, index }) {
  const time = alert.timestamp
    ? formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })
    : 'just now'

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04 }}
      style={{
        background: `rgba(${alert.severity === 'CRITICAL' ? '80,0,0' : alert.severity === 'HIGH' ? '60,30,0' : '40,35,0'}, 0.3)`,
        border: `1px solid ${severityColor(alert.severity)}30`,
        borderLeft: `3px solid ${severityColor(alert.severity)}`,
        borderRadius: 8,
        padding: '10px 12px',
        marginBottom: 8,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontWeight: 600,
            fontSize: 12,
            color: 'var(--text-primary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            marginBottom: 3
          }}>
            {alert.facility_name || 'Unknown Facility'}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
            {alert.country || ''} · {time}
          </div>
        </div>
        <div style={{ marginLeft: 8, textAlign: 'right' }}>
          <span className={`badge ${severityClass(alert.severity)}`}>
            {alert.severity}
          </span>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            fontWeight: 700,
            color: severityColor(alert.severity),
            marginTop: 4
          }}>
            {Number(alert.emission_rate_kg_hr || 0).toFixed(0)} kg/hr
          </div>
        </div>
      </div>
    </motion.div>
  )
}

export default function AlertPanel({ maxItems = 8 }) {
  const liveAlerts = useStore(s => s.liveAlerts)
  const alerts = useStore(s => s.alerts)

  // Merge live + historical, deduplicate by id, remove LOW severity
  const allAlerts = [...liveAlerts, ...alerts]
    .filter((a, i, arr) => arr.findIndex(x => x.id === a.id) === i)
    .filter(a => a.severity !== 'LOW')
    .slice(0, maxItems)

  const criticalCount = allAlerts.filter(a => a.severity === 'CRITICAL').length

  return (
    <div>
      <div className="section-header">
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: criticalCount > 0 ? 'var(--neon-red)' : 'var(--neon-green)',
          boxShadow: criticalCount > 0 ? '0 0 8px rgba(255,68,68,0.8)' : '0 0 8px rgba(0,255,136,0.6)',
          animation: criticalCount > 0 ? 'blink 0.8s infinite' : 'none'
        }} />
        <h3>Live Alerts</h3>
        {criticalCount > 0 && (
          <span className="badge badge-critical">{criticalCount} CRITICAL</span>
        )}
      </div>

      {allAlerts.length === 0 ? (
        <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '20px 0', textAlign: 'center' }}>
          Monitoring for emissions...
        </div>
      ) : (
        <AnimatePresence>
          {allAlerts.map((alert, i) => (
            <AlertItem key={alert.id || i} alert={alert} index={i} />
          ))}
        </AnimatePresence>
      )}
    </div>
  )
}
