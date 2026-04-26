import LoadingProgressBar from './LoadingProgressBar'

const LoadingOverlay = ({ message = 'Analyzing Resume...', visible }) => {
  if (!visible) return null

  return (
    <div className="loader-overlay" aria-live="polite" aria-busy="true">
      <div className="loader-blobs">
        <div className="loader-blob loader-blob-a" />
        <div className="loader-blob loader-blob-b" />
      </div>

      <div className="loader-card glass">
        <p className="loader-title">{message}</p>
        <LoadingProgressBar />
        <p className="loader-subtitle">Screening candidate data with AI scoring engine</p>
      </div>
    </div>
  )
}

export default LoadingOverlay
