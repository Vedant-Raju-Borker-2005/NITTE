import { useState } from 'react'
import { Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import useStore from '../../store/useStore.js'
import { getAlerts } from '../../api/client.js'
import GlobePage from '../../pages/GlobePage.jsx'
import DetectionPage from '../../pages/DetectionPage.jsx'
import FacilitiesPage from '../../pages/FacilitiesPage.jsx'
import AlertsPage from '../../pages/AlertsPage.jsx'
import ReportsPage from '../../pages/ReportsPage.jsx'
import UploadPage from '../../pages/UploadPage.jsx'
import HomeDashboard from './HomeDashboard.jsx'
import styles from './Dashboard.module.css'

const NAV_ITEMS = [
  { path: '/',            icon: '📊', label: 'Dashboard',   id: 'nav-home' },
  { path: '/globe',       icon: '🌍', label: 'Globe',       id: 'nav-globe' },
  { path: '/detect',      icon: '📡', label: 'Detect',      id: 'nav-detect' },
  { path: '/upload',      icon: '🚁', label: 'Drone Upload', id: 'nav-upload' },
  { path: '/facilities',  icon: '🏭', label: 'Facilities',  id: 'nav-facilities' },
  { path: '/alerts',      icon: '🚨', label: 'Alerts',      id: 'nav-alerts' },
  { path: '/reports',     icon: '📄', label: 'Reports',     id: 'nav-reports' },
]

export default function Dashboard() {
  const liveAlerts = useStore(s => s.liveAlerts)
  const { data } = useQuery({
    queryKey: ['alerts', 'dashboard'],
    queryFn: () => getAlerts({ limit: 100 }),
    refetchInterval: 30000,
  })
  const fetchedAlerts = data?.alerts || []
  const mergedAlerts = [...liveAlerts, ...fetchedAlerts].filter(
    (a, i, arr) => arr.findIndex(x => x.id === a.id) === i
  )
  const criticalCount = mergedAlerts.filter(a => a.severity === 'CRITICAL').length

  return (
    <div className={styles.shell}>
      {/* ── Top Bar ── */}
      <header className={styles.topbar}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>🛰️</span>
          <div>
            <span className={styles.logoName}>MethaneX</span>
            <span className={styles.logoTag}>Platform · v2.0</span>
          </div>
        </div>

        <nav className={styles.nav}>
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              id={item.id}
              className={({ isActive }) =>
                `${styles.navItem} ${isActive ? styles.navActive : ''}`
              }
            >
              <span className={styles.navIcon}>{item.icon}</span>
              <span className={styles.navLabel}>{item.label}</span>
              {item.label === 'Alerts' && criticalCount > 0 && (
                <span className={styles.alertBadge}>{criticalCount}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className={styles.status}>
          <span className={styles.statusDot} />
          <span className={styles.statusText}>LIVE</span>
          <span className={styles.statusSep}>·</span>
          <span className={styles.statusText} style={{ color: 'var(--text-secondary)' }}>
            {mergedAlerts.length} events
          </span>
        </div>
      </header>

      {/* ── Main Content ── */}
      <main className={styles.main}>
        <AnimatePresence mode="wait">
          <Routes>
            <Route path="/"           element={<PageWrap><HomeDashboard /></PageWrap>} />
            <Route path="/globe"      element={<PageWrap><GlobePage /></PageWrap>} />
            <Route path="/detect"     element={<PageWrap><DetectionPage /></PageWrap>} />
            <Route path="/upload"     element={<PageWrap><UploadPage /></PageWrap>} />
            <Route path="/facilities" element={<PageWrap><FacilitiesPage /></PageWrap>} />
            <Route path="/alerts"     element={<PageWrap><AlertsPage /></PageWrap>} />
            <Route path="/reports"    element={<PageWrap><ReportsPage /></PageWrap>} />
          </Routes>
        </AnimatePresence>
      </main>
    </div>
  )
}

function PageWrap({ children }) {
  return (
    <motion.div
      key="page"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.25 }}
      style={{ height: '100%', width: '100%' }}
    >
      {children}
    </motion.div>
  )
}
