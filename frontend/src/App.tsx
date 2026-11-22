import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from '@/components/Layout'
import Dashboard from '@/pages/Dashboard'

// Today loads with the app; every other page is its own chunk, fetched the first time it is opened.
const JobDetail = lazy(() => import('@/pages/JobDetail'))
const Jobs = lazy(() => import('@/pages/Jobs'))
const ResumeBank = lazy(() => import('@/pages/ResumeBank'))
const Automations = lazy(() => import('@/pages/Automations'))
const Settings = lazy(() => import('@/pages/Settings'))
const SkillGaps = lazy(() => import('@/pages/SkillGaps'))
const Setup = lazy(() => import('@/pages/Setup'))
const Tracker = lazy(() => import('@/pages/Tracker'))

export default function App() {
  return (
    <Routes>
      <Route path="setup" element={<Suspense fallback={null}><Setup /></Suspense>} />
      {/* Layout wraps its page in Suspense, so the sidebar stays put while a page chunk loads. */}
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="jobs" element={<Jobs />} />
        <Route path="jobs/:id" element={<JobDetail />} />
        <Route path="tracker" element={<Tracker />} />
        <Route path="resume" element={<ResumeBank />} />
        <Route path="settings" element={<Settings />} />
        <Route path="skill-gaps" element={<SkillGaps />} />
        <Route path="automations" element={<Automations />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
