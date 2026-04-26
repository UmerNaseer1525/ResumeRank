import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import {
  getReducedMotionPreference,
  setReducedMotionPreference,
} from '../utils/motionPreferences'

const MotionToggle = () => {
  const [isReduced, setIsReduced] = useState(() => getReducedMotionPreference())

  useEffect(() => {
    const sync = (event) => setIsReduced(Boolean(event.detail))
    window.addEventListener('rr-motion-change', sync)
    return () => window.removeEventListener('rr-motion-change', sync)
  }, [])

  const handleToggle = () => {
    const next = !isReduced
    setIsReduced(next)
    setReducedMotionPreference(next)
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      className="inline-flex items-center gap-1.5 rounded-xl border border-white/25 bg-white/10 px-3 py-2 text-xs font-semibold text-white transition hover:bg-white/20"
      aria-pressed={isReduced}
      title={isReduced ? 'Enable full animations' : 'Reduce animations'}
    >
      <Sparkles size={14} />
      {isReduced ? 'Motion Off' : 'Motion On'}
    </button>
  )
}

export default MotionToggle
