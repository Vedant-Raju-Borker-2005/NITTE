import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', height: '100%',
        background: 'var(--bg-void)', color: 'var(--text-primary)', padding: 40,
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
        <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: 'var(--neon-red)' }}>
          Page failed to load
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20, maxWidth: 380 }}>
          An error occurred rendering this page. This is usually a temporary issue.
        </p>
        {import.meta.env.DEV && this.state.error && (
          <pre style={{
            fontSize: 10, color: 'var(--neon-amber)', background: 'var(--bg-card)',
            border: '1px solid var(--border)', borderRadius: 8, padding: 12,
            maxWidth: 600, overflowX: 'auto', textAlign: 'left', marginBottom: 20,
          }}>
            {this.state.error.toString()}
          </pre>
        )}
        <button
          className="btn btn-primary"
          onClick={() => this.setState({ hasError: false, error: null })}
        >
          ↺ Retry
        </button>
      </div>
    )
  }
}
