import React from 'react'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, info) {
    console.error('[MethSight Error]', error, info)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', height: '100vh',
          background: '#050810', color: '#e8f0fe', fontFamily: 'Inter, sans-serif',
          padding: 40, textAlign: 'center'
        }}>
          <div style={{ fontSize: 64, marginBottom: 20 }}>⚠️</div>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: '#ff4444', marginBottom: 12 }}>
            Component Error
          </h2>
          <pre style={{
            background: 'rgba(255,68,68,0.1)', border: '1px solid rgba(255,68,68,0.3)',
            borderRadius: 8, padding: 16, fontSize: 12, color: '#ff8888',
            maxWidth: 600, overflow: 'auto', textAlign: 'left'
          }}>
            {this.state.error?.toString()}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary
