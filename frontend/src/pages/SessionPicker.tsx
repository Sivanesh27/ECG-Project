import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import type { SessionRow } from '../types'
import { ErrorBox, SignalQualityBadge, Spinner } from '../components/ui'
import { fmt, fmtDate, fmtDuration } from '../utils/format'

/** Sidebar entries such as "HRV analysis" are cross-session: pick a session, then open the matching tab. */
export default function SessionPicker({ tab, title }: { tab: string; title: string }) {
  const [rows, setRows] = useState<SessionRow[] | null>(null); const [err, setErr] = useState('')
  useEffect(() => { api.sessions().then((r) => setRows(r.items)).catch((e) => setErr(e.message)) }, [])
  if (err) return <ErrorBox message={err} />
  if (!rows) return <Spinner />
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">{title}</h1>
      <p className="text-muted">Choose a session to open its {title.toLowerCase()}.</p>
      {!rows.length && <p className="panel p-6">No sessions yet. <Link className="text-orange hover:underline" to="/app/new">Upload a recording</Link> to begin.</p>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((r) => (
          <Link key={r.id} to={`/app/sessions/${r.id}/${tab}`} className="panel p-4 hover:border-orange block">
            <div className="flex justify-between gap-2"><span className="font-semibold">{r.name}</span><SignalQualityBadge status={r.quality} /></div>
            <p className="text-sm text-muted mt-1">{r.subject} · {fmtDate(r.start)}</p>
            <p className="text-sm mt-3 readout">{fmtDuration(r.durationS)} · avg {fmt(r.summary?.avg_hr, 0)} bpm · RMSSD {fmt(r.summary?.rmssd, 1)} ms</p>
          </Link>))}
      </div>
    </div>
  )
}
