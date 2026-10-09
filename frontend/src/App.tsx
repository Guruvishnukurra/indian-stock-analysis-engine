import { MotionConfig } from 'motion/react'
import { Navigate, Route, Routes, useLocation } from 'react-router'
import { CommandPalette } from './components/CommandPalette'
import { ComparePage } from './pages/Compare'
import { EvidencePage } from './pages/Evidence'
import { HomePage } from './pages/Home'
import { HowItWorksPage } from './pages/HowItWorks'
import { PrintReportPage } from './pages/PrintReport'
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
        <Route path="/s/:ticker/report" element={<PrintReportPage />} />
        <Route path="/how-it-works" element={<HowItWorksPage />} />
        <Route path="/evidence" element={<EvidencePage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <CommandPalette />
    </MotionConfig>
  )
}
