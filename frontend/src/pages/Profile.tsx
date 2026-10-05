import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../hooks/useAuth'
import { ErrorBox } from '../components/ui'

export default function Profile() {
  const { user, logout } = useAuth(); const nav = useNavigate()
  const [pw, setPw] = useState(''); const [err, setErr] = useState('')
  const del = async () => {
    if (!confirm('Permanently delete your account and ALL recordings, analyses and reports? This cannot be undone.')) return
    try { await api.deleteAccount(pw); await logout(); nav('/') } catch (e: any) { setErr(e.message) }
  }
  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-3xl font-bold">Profile</h1>
      <dl className="panel p-5 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm"><dt className="text-muted">Name</dt><dd>{user?.name}</dd><dt className="text-muted">Email</dt><dd>{user?.email}</dd>
        <dt className="text-muted">Institution</dt><dd>{user?.organization || '—'}</dd><dt className="text-muted">Role</dt><dd>{user?.role || '—'}</dd></dl>
      <section className="panel p-5 space-y-3 border-red-900"><h2 className="font-semibold">Delete account</h2>
        <p className="text-sm text-muted">Removes your account, uploaded files, subjects, sessions, analyses and reports.</p>{err && <ErrorBox message={err} />}
        <label className="label" htmlFor="dp">Confirm with your password</label><input id="dp" type="password" className="field" value={pw} onChange={(e) => setPw(e.target.value)} />
        <button className="btn-danger" disabled={!pw} onClick={del}>Delete my account</button></section>
    </div>
  )
}
