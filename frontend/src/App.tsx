import type { ReactElement } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import AppLayout from './layouts/AppLayout'
import Landing from './pages/Landing'
import { Forgot, Login, Register, ResetPassword } from './pages/AuthPages'
import Dashboard from './pages/Dashboard'
import NewAnalysis from './pages/NewAnalysis'
import Sessions from './pages/Sessions'
import SessionView from './pages/SessionView'
import SessionPicker from './pages/SessionPicker'
import Settings from './pages/Settings'
import Profile from './pages/Profile'
import { Spinner } from './components/ui'

function Protected({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth()
  const loc = useLocation()
  if (loading) return <Spinner label="Checking session" />
  return user ? children : <Navigate to="/login" state={{ from: loc.pathname }} replace />
}

export default function App() {
  const { user } = useAuth()
  return (
    <Routes>
      <Route path="/" element={user ? <Navigate to="/app" replace /> : <Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<Forgot />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/app" element={<Protected><AppLayout /></Protected>}>
        <Route index element={<Dashboard />} />
        <Route path="new" element={<NewAnalysis />} />
        <Route path="sessions" element={<Sessions />} />
        <Route path="sessions/:id/*" element={<SessionView />} />
        <Route path="hr" element={<SessionPicker tab="hr" title="HR analysis" />} />
        <Route path="hrv" element={<SessionPicker tab="hrv" title="HRV analysis" />} />
        <Route path="training" element={<SessionPicker tab="training" title="Training load" />} />
        <Route path="movement" element={<SessionPicker tab="movement" title="Movement" />} />
        <Route path="reports" element={<SessionPicker tab="report" title="Reports" />} />
        <Route path="settings" element={<Settings />} />
        <Route path="profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
