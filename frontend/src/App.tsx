import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from '@/components/Layout'
import Dashboard from '@/pages/Dashboard'
import JobDetail from '@/pages/JobDetail'
import Jobs from '@/pages/Jobs'
import ResumeBank from '@/pages/ResumeBank'
import Automations from '@/pages/Automations'
import Settings from '@/pages/Settings'
import SkillGaps from '@/pages/SkillGaps'
import Setup from '@/pages/Setup'
import Tracker from '@/pages/Tracker'

export default function App() {
  return (
    <Routes>
      <Route path="setup" element={<Setup />} />
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
