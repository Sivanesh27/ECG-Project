import { useRef, useState, type ReactNode } from 'react'
import { fmt, NA } from '../utils/format'
import type { Quality, Warning, Zone } from '../types'

export function InfoTooltip({ text }: { text: string }) {
  return (
    <span className="relative inline-flex group align-middle">
      <button type="button" aria-label={`About: ${text}`} className="ml-1 h-4 w-4 text-[10px] leading-4 text-center border border-line text-muted hover:text-orange hover:border-orange rounded-full">i</button>
      <span role="tooltip" className="pointer-events-none absolute z-30 left-1/2 -translate-x-1/2 top-6 w-64 p-2 text-xs text-white bg-ink border border-orange opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">{text}</span>
    </span>
  )
}

export function MetricCard({ label, value, unit, hint, sub, tip, big }: { label: string; value: number | string | null | undefined; unit?: string; hint?: string; sub?: ReactNode; tip?: string; big?: boolean }) {
  const na = value === null || value === undefined || value === NA
  return (
    <div className="panel p-4 min-w-0">
      <div className="text-sm text-muted flex items-center">{label}{tip && <InfoTooltip text={tip} />}</div>
      <div className={`readout mt-1 ${big ? 'text-4xl' : 'text-3xl'} ${na ? 'text-neutral-600' : 'text-white'}`} title={na ? 'N/A — insufficient valid data' : undefined}>
        {na ? NA : typeof value === 'number' ? fmt(value, 1) : value}
        {!na && unit && <span className="text-sm text-orange ml-1.5 font-sans">{unit}</span>}
      </div>
      {hint && <p className="text-xs text-muted mt-1.5 leading-snug">{hint}</p>}
      {sub && <div className="mt-2 text-xs">{sub}</div>}
    </div>
  )
}

export function ChartCard({ title, subtitle, actions, children }: { title: string; subtitle?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="panel" aria-label={title}>
      <header className="flex items-start justify-between gap-3 px-4 py-3 border-b border-line">
        <div><h3 className="font-semibold">{title}</h3>{subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}</div>
        {actions}
      </header>
      <div className="p-3">{children}</div>
    </section>
  )
}

export function WarningBanner({ w }: { w: Warning }) {
  const tone = w.level === 'error' ? 'border-red-700 bg-red-950/40' : w.level === 'warn' ? 'border-orange bg-orange/10' : 'border-line bg-panel'
  const icon = w.level === 'error' ? '✖' : w.level === 'warn' ? '▲' : 'ⓘ'
  return <div role={w.level === 'info' ? 'note' : 'alert'} className={`border-l-4 ${tone} px-3 py-2 text-sm flex gap-2`}><span aria-hidden className="text-orange">{icon}</span><span><span className="sr-only">{w.level}: </span>{w.message}</span></div>
}

export function SignalQualityBadge({ status }: { status: Quality }) {
  const s = status || 'UNKNOWN'
  const map: Record<string, [string, string]> = { GOOD: ['●', 'border-green-700 text-green-300'], ACCEPTABLE: ['◐', 'border-orange text-orange'], POOR: ['▲', 'border-red-700 text-red-300'], UNKNOWN: ['○', 'border-line text-muted'] }
  const [ic, cls] = map[s] || map.UNKNOWN
  return <span className={`inline-flex items-center gap-1.5 border px-2 py-0.5 text-xs font-semibold ${cls}`}><span aria-hidden>{ic}</span>{s === 'UNKNOWN' ? 'No ECG' : s}</span>
}

export const ZONE_COLORS = ['#4B4B4B', '#FFC9A3', '#FFA561', '#FF7A18', '#E85D00', '#B33F00']
export function ZoneBadge({ z }: { z: Pick<Zone, 'zone' | 'label'> }) {
  return <span className="inline-flex items-center gap-1.5 text-xs"><span className="h-2.5 w-2.5" style={{ background: ZONE_COLORS[z.zone % 6] }} aria-hidden />{z.label}</span>
}

export function DataTable<T>({ cols, rows, empty = 'No data', rowKey, maxHeight }: { cols: { key: string; head: string; render: (r: T) => ReactNode; align?: 'right' }[]; rows: T[]; empty?: string; rowKey: (r: T, i: number) => string; maxHeight?: number }) {
  if (!rows.length) return <p className="text-sm text-muted p-4">{empty}</p>
  return (
    <div className="overflow-auto" style={{ maxHeight }}>
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-ink"><tr>{cols.map((c) => <th key={c.key} scope="col" className={`text-left font-semibold px-3 py-2 text-muted border-b border-line whitespace-nowrap ${c.align === 'right' ? 'text-right' : ''}`}>{c.head}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={rowKey(r, i)} className="border-b border-line/60 hover:bg-white/[0.03]">{cols.map((c) => <td key={c.key} className={`px-3 py-2 whitespace-nowrap ${c.align === 'right' ? 'text-right readout' : ''}`}>{c.render(r)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

export function ProgressStepper({ steps, current, failed }: { steps: string[]; current: number; failed?: boolean }) {
  return (
    <ol className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3" aria-label="Processing progress">
      {steps.map((s, i) => {
        const done = i < current || (i === current && s === 'Complete'); const active = i === current && !done
        return (
          <li key={s} aria-current={active ? 'step' : undefined} className={`flex items-center gap-2 px-3 py-1.5 text-sm border ${active ? (failed ? 'border-red-700' : 'border-orange text-orange') : done ? 'border-line text-white' : 'border-line/50 text-neutral-600'}`}>
            <span aria-hidden className="w-4 text-center">{done ? '✓' : active ? (failed ? '✖' : '▸') : '·'}</span>{s}
          </li>
        )
      })}
    </ol>
  )
}

export function UploadDropzone({ onFile, busy, progress, accept = '.zip,.csv,.xlsx' }: { onFile: (f: File) => void; busy?: boolean; progress?: number; accept?: string }) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f) }}
      className={`border-2 border-dashed px-6 py-12 text-center ${over ? 'border-orange bg-orange/5' : 'border-line'}`}>
      <p className="text-lg font-semibold">Drop a recording here</p>
      <p className="text-sm text-muted mt-1">ZIP exports, or CSV / XLSX with timestamp and ecg, rr or hr columns</p>
      <input ref={input} type="file" accept={accept} className="sr-only" aria-label="Choose a file to upload" onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = '' }} />
      <button type="button" className="btn-primary mt-5" disabled={busy} onClick={() => input.current?.click()}>{busy ? `Uploading… ${progress ?? 0}%` : 'Choose file'}</button>
      {busy && <div className="mt-4 h-1.5 bg-line" role="progressbar" aria-valuenow={progress ?? 0} aria-valuemin={0} aria-valuemax={100}><div className="h-full bg-orange" style={{ width: `${progress ?? 0}%` }} /></div>}
    </div>
  )
}

export function ExportMenu({ items }: { items: { label: string; href: string }[] }) {
  return (
    <details className="relative">
      <summary className="btn-ghost cursor-pointer list-none">Export</summary>
      <div className="absolute right-0 mt-1 z-30 w-52 panel">{items.map((i) => <a key={i.label} href={i.href} className="block px-3 py-2 text-sm hover:bg-white/5 hover:text-orange">{i.label}</a>)}</div>
    </details>
  )
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return <div role="status" className="flex items-center gap-3 p-8 text-muted"><span className="h-4 w-4 border-2 border-orange border-t-transparent rounded-full animate-spin" aria-hidden />{label}…</div>
}

export function ErrorBox({ message }: { message: string }) {
  return <div role="alert" className="border border-red-800 bg-red-950/30 text-red-200 text-sm px-4 py-3">{message}</div>
}

export function DateRangeSelector({ from, to, onChange }: { from: string; to: string; onChange: (f: string, t: string) => void }) {
  return (
    <div className="flex items-end gap-2">
      <label className="text-sm text-muted">From<input type="date" className="field mt-1" value={from} onChange={(e) => onChange(e.target.value, to)} /></label>
      <label className="text-sm text-muted">To<input type="date" className="field mt-1" value={to} onChange={(e) => onChange(from, e.target.value)} /></label>
      {(from || to) && <button className="btn-ghost" onClick={() => onChange('', '')}>Clear</button>}
    </div>
  )
}

export function ChartToolbar({ children }: { children: ReactNode }) {
  return <div role="toolbar" aria-label="Chart controls" className="flex flex-wrap items-center gap-1.5">{children}</div>
}
