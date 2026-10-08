import { Compass } from '@phosphor-icons/react'
import { createBrowserRouter, Link, RouterProvider } from 'react-router-dom'
import { AuthProvider, RequireAuth } from '@/app/auth'
import { Shell } from '@/app/shell'
import { EmptyState } from '@/components/kit'
import { AppliedPage } from '@/pages/applied'
import { DraftPage } from '@/pages/draft'
import { LoginPage } from '@/pages/login'
import { ReadyPage } from '@/pages/ready'
import { RunPage, RunsPage } from '@/pages/runs'
import { SchedulesPage } from '@/pages/schedules'
import { SettingsPage } from '@/pages/settings'
import { TodayPage } from '@/pages/today'

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: <RequireAuth><Shell /></RequireAuth>,
    children: [
      { index: true, element: <TodayPage /> },
      { path: 'ready', element: <ReadyPage /> },
      { path: 'applied', element: <AppliedPage /> },
      { path: 'draft', element: <DraftPage /> },
      { path: 'runs', element: <RunsPage /> },
      { path: 'runs/:id', element: <RunPage /> },
      { path: 'schedules', element: <SchedulesPage /> },
      { path: 'settings', element: <SettingsPage /> },
      {
        path: '*',
        element: <EmptyState icon={Compass} title="No page here"
          body="The link may be old. Today has everything that is ready."
          action={<Link to="/" className="text-sm font-medium text-primary underline-offset-4 hover:underline">Go to Today</Link>} />,
      },
    ],
  },
])

export default function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  )
}
