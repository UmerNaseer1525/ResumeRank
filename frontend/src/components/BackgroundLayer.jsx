const BackgroundLayer = () => {
  return (
    <div className="background-layer" aria-hidden="true">
      <div className="background-gradient" />
      <div className="background-blobs">
        <div className="blob blob-1" />
        <div className="blob blob-2" />
        <div className="blob blob-3" />
        <div className="blob blob-4" />
      </div>
      <div className="background-grid" />
    </div>
  )
}

export default BackgroundLayer
