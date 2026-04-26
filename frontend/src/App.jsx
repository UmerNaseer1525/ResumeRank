import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import AuthLayout from './layouts/AuthLayout'
import CandidateAnalysisPage from './pages/CandidateAnalysisPage'
import DashboardPage from './pages/DashboardPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import ProfilePage from './pages/ProfilePage'
import RankingResultsPage from './pages/RankingResultsPage'
import ResumeAnalysisPage from './pages/ResumeAnalysisPage'
import ResumeProcessingPage from './pages/ResumeProcessingPage'
import SignupPage from './pages/SignupPage'
import UploadPage from './pages/UploadPage'
import JobsPage from './pages/JobsPage'
import JobCreatePage from './pages/JobCreatePage'
import JobDetailPage from './pages/JobDetailPage'
import ProtectedRoute from './components/ProtectedRoute'
import PublicOnlyRoute from './components/PublicOnlyRoute'
import {
  applyReducedMotionClass,
  getReducedMotionPreference,
} from './utils/motionPreferences'

const ScrollRevealManager = () => {
  const location = useLocation()

  useEffect(() => {
    const elements = document.querySelectorAll('[data-reveal]')
    if (!elements.length) return

    const revealIfVisible = (element) => {
      const rect = element.getBoundingClientRect()
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight
      const isInView = rect.top < viewportHeight * 0.92 && rect.bottom > 0

      if (isInView) {
        element.classList.add('is-visible')
        return true
      }

      return false
    }

    const observer = new IntersectionObserver(
      (entries, currentObserver) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible')
            currentObserver.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.16 },
    )

    elements.forEach((element) => {
      if (!revealIfVisible(element)) {
        observer.observe(element)
      }
    })

    const frameId = window.requestAnimationFrame(() => {
      elements.forEach((element) => revealIfVisible(element))
    })

    return () => {
      observer.disconnect()
      window.cancelAnimationFrame(frameId)
    }
  }, [location.pathname])

  return null
}

const App = () => {
  const location = useLocation()

  useEffect(() => {
    applyReducedMotionClass(getReducedMotionPreference())
  }, [])

  return (
    <>
      <ScrollRevealManager />
      <div key={location.pathname} className="route-enter">
        <Routes location={location}>
          <Route path="/" element={<HomePage />} />

          <Route element={<PublicOnlyRoute />}>
            <Route element={<AuthLayout title="Login" />}>
              <Route path="/login" element={<LoginPage />} />
            </Route>

            <Route element={<AuthLayout title="Sign Up" />}>
              <Route path="/signup" element={<SignupPage />} />
            </Route>
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/jobs" element={<JobsPage />} />
              <Route path="/jobs/create" element={<JobCreatePage />} />
              <Route path="/jobs/:jobId" element={<JobDetailPage />} />
              <Route path="/resume-processing" element={<ResumeProcessingPage />} />
              <Route path="/resume-analysis" element={<ResumeAnalysisPage />} />
              <Route path="/ranking-results" element={<RankingResultsPage />} />
              <Route
                path="/candidate-analysis/:id"
                element={<CandidateAnalysisPage />}
              />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>
          </Route>

          <Route path="/home" element={<Navigate to="/" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </div>
    </>
  )
}

export default App
