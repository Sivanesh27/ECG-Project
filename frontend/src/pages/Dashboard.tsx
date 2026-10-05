import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../hooks/useAuth'
import type { Dashboard as D, SessionRow } from '../types'
import { DataTable, ErrorBox, MetricCard, SignalQualityBadge, Spinner } from '../components/ui'
import { fmt, fmtDate, fmtDuration } from '../utils/format'

export function SessionsTable({ rows, onDelete }: { rows: SessionRow[]; onDelete?: (id: string) => void }) {
  return (
    <DataTable rows={rows} rowKey={(r) => r.id} empty="No sessions yet."
      cols={[
        { key: 's', head: 'Session', render: (r) => <Link className="text-orange hover:underline" to={`/app/sessions/${r.id}`}>{r.name}</Link> },
        { key: 'sub', head: 'Subject', render: (r) => r.subject },
        { key: 'd', head: 'Date', render: (r) => fmtDate(r.start) },
        { key: 'du', head: 'Duration', align: 'right', render: (r) => fmtDuration(r.durationS) },
        { key: 'a', head: 'Avg HR', align: 'right', render: (r) => fmt(r.summary?.avg_hr, 1) },
        { key: 'm', head: 'Max HR', align: 'right', render: (r) => fmt(r.summary?.max_hr, 1) },
        { key: 'r', head: 'RMSSD (ms)', align: 'right', render: (r) => fmt(r.summary?.rmssd, 1) },
        { key: 't', head: 'Training load', align: 'right', render: (r) => fmt(r.summary?.training_load_source ?? r.summary?.training_load_calc, 2) },
        { key: 'q', head: 'Quality', render: (r) => <SignalQualityBadge status={r.quality} /> },
        { key: 'x', head: 'Actions', render: (r) => (
          <span className="flex gap-3 text-sm">
            <Link className="hover:text-orange" to={`/app/sessions/${r.id}`}>View</Link>
            <Link className="hover:text-orange" to={`/app/sessions/${r.id}/report`}>Report</Link>
            {onDelete && <button className="text-red-300 hover:underline" onClick={() => { if (confirm(`Delete session ${r.name} and all its analysis data?`)) onDelete(r.id) }}>Delete</button>}
          </span>) },
      ]} />
  )
}

export default function Dashboard() {
  const { user } = useAuth(); const nav = useNavigate()
  const [d, setD] = useState<D | null>(null); const [err, setErr] = useState('')
  const load = () => api.dashboard().then(setD).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])
  if (err) return <ErrorBox message={err} />
  if (!d) return <Spinner />
  const k = d.kpis
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-3xl font-bold">ECG / HRV analytics</h1><p className="text-muted mt-1">Welcome, {user?.name}. {d.total_sessions ? 'Open a recent session or add a new recording.' : 'Upload a recording to begin analysis.'}</p></div>
        <button className="btn-primary text-base px-6 py-3" onClick={() => nav('/app/new')}>Upload a recording</button>
      </div>
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        <MetricCard label="Total sessions" value={String(d.total_sessions)} />
        <MetricCard label="Latest HR" value={k.latest_hr} unit="bpm" hint="Average of latest session" />
        <MetricCard label="Latest HRV (RMSSD)" value={k.latest_rmssd} unit="ms" hint="Short-term, from ECG windows" />
        <MetricCard label="Latest training load" value={k.latest_training_load} hint="Source dataset value" />
        <MetricCard label="Latest movement load" value={k.latest_movement_load} />
        <MetricCard label="Average HR" value={d.average_hr_recent} unit="bpm" hint="Across recent sessions" />
        <MetricCard label="Latest quality" value={k.latest_quality ?? null} />
      </div>
      <section className="panel"><header className="px-4 py-3 border-b border-line flex justify-between"><h2 className="font-semibold">Recent sessions</h2><Link to="/app/sessions" className="text-sm text-orange hover:underline">All sessions</Link></header>
        <SessionsTable rows={d.recent} onDelete={async (id) => { await api.deleteSession(id); load() }} /></section>
    </div>
  )
}
