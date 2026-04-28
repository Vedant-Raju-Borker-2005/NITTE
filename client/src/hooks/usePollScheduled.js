/**
 * usePollScheduled.js
 * Polls /scan/scheduled every intervalMs and calls onData(results).
 * Returns { status: 'polling'|'error'|'idle', lastUpdated }.
 */
import { useEffect, useRef, useState } from 'react'
import api from '../api/client.js'

export default function usePollScheduled(onData, intervalMs = 30000) {
  const [status, setStatus] = useState('idle')
  const [lastUpdated, setLastUpdated] = useState(null)
  const timerRef = useRef(null)
  const onDataRef = useRef(onData)
  onDataRef.current = onData

  const poll = async () => {
    try {
      const r = await api.get('/scan/scheduled')
      const results = r.data?.results || []
      onDataRef.current(results)
      setStatus('polling')
      setLastUpdated(new Date())
    } catch {
      setStatus('error')
    }
  }

  useEffect(() => {
    poll()
    timerRef.current = setInterval(poll, intervalMs)
    return () => clearInterval(timerRef.current)
  }, [intervalMs])

  return { status, lastUpdated }
}
