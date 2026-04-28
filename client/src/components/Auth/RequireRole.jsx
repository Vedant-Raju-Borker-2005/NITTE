import { useState, useEffect } from 'react'

export default function RequireRole({ role, children }) {
  // Mock authentication logic. In a real app, decode JWT here.
  const [currentUserRole, setCurrentUserRole] = useState('regulator') // default to regulator for demo

  // For demonstration, we can toggle this using localStorage or a debug window variable
  useEffect(() => {
    const override = localStorage.getItem('methanex_role')
    if (override) setCurrentUserRole(override)
  }, [])

  if (currentUserRole !== role && currentUserRole !== 'admin') {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <h2>Access Denied</h2>
        <p>This page requires <strong>{role}</strong> privileges.</p>
        <p style={{ fontSize: '12px', marginTop: '10px' }}>Current role: {currentUserRole}</p>
        <button className="btn btn-ghost" onClick={() => {
          localStorage.setItem('methanex_role', role)
          window.location.reload()
        }} style={{ marginTop: '20px' }}>
          Simulate {role} Login (Demo)
        </button>
      </div>
    )
  }

  return children
}
