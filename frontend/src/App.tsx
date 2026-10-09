import { MotionConfig } from 'motion/react'
import { Navigate, Route, Routes, useLocation } from 'react-router'
import { HomePage } from './pages/Home'
import { ReportPage } from './pages/Report'

// Old links used /?t=TCS.NS; send them to the report route.
function Root() {
  const t = new URLSearchParams(useLocation().search).get('t')
  return t ? <Navigate to={`/s/${t.replace(/\.(NS|BO)$/i, '')}`} replace /> : <HomePage />
}

export default function App() {
  return (
    // Respect the OS reduced-motion setting for every motion component.
    <MotionConfig reducedMotion="user">
      <Routes>
        <Route path="/" element={<Root />} />
        <Route path="/s/:ticker" element={<ReportPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </MotionConfig>
  )
}
