/**
 * SkeletonCard — shimmer loading placeholder.
 * Usage: <SkeletonCard lines={3} height={80} />
 */
export default function SkeletonCard({ lines = 2, height = 60, style = {} }) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      padding: 14,
      height,
      overflow: 'hidden',
      ...style,
    }}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{
            height: 10,
            borderRadius: 5,
            marginBottom: i < lines - 1 ? 8 : 0,
            width: i === lines - 1 ? '60%' : '100%',
          }}
        />
      ))}
    </div>
  )
}
