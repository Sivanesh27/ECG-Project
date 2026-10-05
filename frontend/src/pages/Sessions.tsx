import { useEffect, useMemo, useState } from 'react'
import { api } from '../services/api'
import type { SessionRow } from '../types'
import { DateRangeSelector, ErrorBox, Spinner } from '../components/ui'
import { SessionsTable } from './Dashboard'

export default function Sessions() {
  const [rows, setRows] = useState<SessionRow[] | null>(null); const [err, setErr] = useState('')
  const [q, setQ] = useState(''); const [from, setFrom] = useState(''); const [to, setTo] = useState('')
  const load = () => api.sessions().then((r) => setRows(r.items)).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])
  const shown = useMemo(() => (rows || []).filter((r) => {
    const t = r.start ? r.start.slice(0, 10) : ''
    return (!q || (r.name + r.subject).toLowerCase().includes(q.toLowerCase())) && (!from || t >= from) && (!to || t <= to)
  }), [rows, q, from, to])
  if (err) return <ErrorBox message={err} />
  if (!rows) return <Spinner />
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">Sessions</h1>
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-sm text-muted">Search<input className="field mt-1" placeholder="Session or subject" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <DateRangeSelector from={from} to={to} onChange={(f, t) => { setFrom(f); setTo(t) }} />
      </div>
      <div className="panel"><SessionsTable rows={shown} onDelete={async (id) => { await api.deleteSession(id); load() }} /></div>
    </div>
  )
}
