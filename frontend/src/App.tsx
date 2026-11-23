import { Navigate, Route } from 'react-router-dom'
import Layout from '@/components/Layout'
import Dashboard from '@/pages/Dashboard'

// Today loads with the app; every other page is its own chunk, loaded by the router the first time it is opened
// (the current page stays on screen until the next one is ready).
const page = (load: () => Promise<{ default: React.ComponentType }>) => async () => ({ Component: (await load()).default })

/** The route tree, used by main.tsx's data router (which the unsaved-changes guard needs). */
export const appRoutes = (
  <>
    <Route path="setup" lazy={page(() => import('@/pages/Setup'))} />
    <Route element={<Layout />}>
      <Route index element={<Dashboard />} />
      <Route path="jobs" lazy={page(() => import('@/pages/Jobs'))} />
      <Route path="jobs/:id" lazy={page(() => import('@/pages/JobDetail'))} />
      <Route path="tracker" lazy={page(() => import('@/pages/Tracker'))} />
      <Route path="resume" lazy={page(() => import('@/pages/ResumeBank'))} />
      <Route path="settings" lazy={page(() => import('@/pages/Settings'))} />
      <Route path="skill-gaps" lazy={page(() => import('@/pages/SkillGaps'))} />
      <Route path="automations" lazy={page(() => import('@/pages/Automations'))} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Route>
  </>
)
