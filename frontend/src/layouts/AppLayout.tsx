import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const NAV = [
  { to: '/app', label: 'Dashboard', end: true }, { to: '/app/new', label: 'New analysis' }, { to: '/app/sessions', label: 'Sessions' },
  { to: '/app/hr', label: 'HR analysis' }, { to: '/app/hrv', label: 'HRV analysis' }, { to: '/app/training', label: 'Training load' },
  { to: '/app/movement', label: 'Movement' }, { to: '/app/reports', label: 'Reports' }, { to: '/app/settings', label: 'Settings' }, { to: '/app/profile', label: 'Profile' },
]

export function Logo() {
  return (
    <span className="inline-flex items-center gap-2 font-semibold tracking-tight">
      <svg width="26" height="16" viewBox="0 0 26 16" aria-hidden><path d="M0 9h6l2-6 4 12 3-9 2 3h9" fill="none" stroke="#FF6A00" strokeWidth="2" strokeLinejoin="round" /></svg>
      <span>ECG<span className="text-orange">/</span>HRV Analytics</span>
    </span>
  )
}

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex flex-col py-2">
      {NAV.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.end} onClick={onNavigate}
          className={({ isActive }) => `px-5 py-2.5 text-sm border-l-2 ${isActive ? 'border-orange text-orange bg-orange/5 font-semibold' : 'border-transparent text-neutral-300 hover:text-white hover:bg-white/5'}`}>
          {n.label}
        </NavLink>
      ))}
    </nav>
  )
}

export function UserMenu() {
  const { user, logout } = useAuth(); const nav = useNavigate()
  return (
    <details className="relative">
      <summary className="list-none cursor-pointer flex items-center gap-2 text-sm px-2 py-1 hover:text-orange">
        <span aria-hidden className="h-7 w-7 bg-orange text-ink font-bold grid place-items-center">{user?.name?.[0]?.toUpperCase()}</span>
        <span className="hidden sm:inline">{user?.name}</span>
      </summary>
      <div className="absolute right-0 mt-1 w-56 panel z-40">
        <p className="px-3 py-2 text-xs text-muted border-b border-line truncate">{user?.email}</p>
        <button className="block w-full text-left px-3 py-2 text-sm hover:bg-white/5" onClick={() => nav('/app/profile')}>Profile</button>
        <button className="block w-full text-left px-3 py-2 text-sm hover:bg-white/5 hover:text-orange" onClick={async () => { await logout(); nav('/') }}>Sign out</button>
      </div>
    </details>
  )
}

export default function AppLayout() {
  const [open, setOpen] = useState(false)
  const nav = useNavigate()
  return (
    <div className="min-h-full flex">
      <aside className="hidden lg:block w-56 shrink-0 bg-ink border-r border-line sticky top-0 h-screen overflow-y-auto">
        <div className="px-5 py-4 border-b border-line"><Logo /></div>
        <Sidebar />
      </aside>
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-20 bg-ink/95 backdrop-blur border-b border-line h-14 px-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button className="lg:hidden btn-ghost px-2 py-1" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(!open)}>☰</button>
            <span className="lg:hidden"><Logo /></span>
          </div>
          <div className="flex items-center gap-3">
            <button className="btn-primary py-1.5" onClick={() => nav('/app/new')}>Upload recording</button>
            <UserMenu />
          </div>
        </header>
        {open && <div className="lg:hidden bg-ink border-b border-line"><Sidebar onNavigate={() => setOpen(false)} /></div>}
        <main className="flex-1 p-4 md:p-6 max-w-[1500px] w-full mx-auto"><Outlet /></main>
        <footer className="px-6 py-3 text-xs text-muted border-t border-line">Research and analysis tool — not a medical device. Does not diagnose any condition.</footer>
      </div>
    </div>
  )
}
