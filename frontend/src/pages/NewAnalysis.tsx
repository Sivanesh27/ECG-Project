import { useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, uploadFile } from '../services/api'
import type { DetectedSession, UploadResult } from '../types'
import { ErrorBox, MetricCard, ProgressStepper, UploadDropzone, WarningBanner } from '../components/ui'
import { useJob } from '../hooks/useJob'
import { bmi, fmt, fmtDate, fmtDuration } from '../utils/format'

type Subj = { name: string; age: string; gender: string; height_cm: string; weight_kg: string; resting_hr: string; max_hr: string; fitness_level: string; activity_type: string; exercise_duration_min: string; notes: string }
const EMPTY: Subj = { name: '', age: '', gender: 'male', height_cm: '', weight_kg: '', resting_hr: '', max_hr: '', fitness_level: '', activity_type: '', exercise_duration_min: '', notes: '' }
const num = (s: string) => (s.trim() === '' ? undefined : Number(s))

export default function NewAnalysis() {
  const nav = useNavigate()
  const [step, setStep] = useState(1)
  const [s, setS] = useState<Subj>(EMPTY)
  const [up, setUp] = useState<UploadResult | null>(null); const [pct, setPct] = useState(0); const [busy, setBusy] = useState(false)
  const [sel, setSel] = useState<Set<string>>(new Set()); const [err, setErr] = useState(''); const [jobId, setJobId] = useState<string | null>(null)
  const { job } = useJob(jobId)
  const b = useMemo(() => bmi(num(s.height_cm), num(s.weight_kg)), [s.height_cm, s.weight_kg])
  const set = (k: keyof Subj) => (e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setS({ ...s, [k]: e.target.value })
  const valid = s.name.trim() && Number(s.age) > 0 && Number(s.age) < 121

  const onFile = async (f: File) => {
    setErr(''); setBusy(true); setPct(0)
    try { const r = await uploadFile(f, setPct); setUp(r); setSel(new Set(r.sessions.map((x) => x.key))); setStep(3) } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  const start = async () => {
    if (!up) return; setErr('')
    const subject = { name: s.name.trim(), age: Number(s.age), gender: s.gender, height_cm: num(s.height_cm), weight_kg: num(s.weight_kg), resting_hr: num(s.resting_hr), max_hr: num(s.max_hr),
      fitness_level: s.fitness_level || undefined, activity_type: s.activity_type || undefined, exercise_duration_min: num(s.exercise_duration_min), notes: s.notes || undefined }
    try { setJobId((await api.process(up.id, subject, [...sel])).job_id); setStep(4) } catch (e: any) { setErr(e.message) }
  }
  const toggle = (k: string) => { const n = new Set(sel); n.has(k) ? n.delete(k) : n.add(k); setSel(n) }

  useEffect(() => {
    if (job?.status !== 'complete' || step !== 4) return
    const h = setTimeout(() => nav(job.sessionIds.length === 1 ? `/app/sessions/${job.sessionIds[0]}` : '/app/sessions'), 600)
    return () => clearTimeout(h)
  }, [job?.status, step])

  return (
    <div className="space-y-6 max-w-5xl">
      <div><h1 className="text-3xl font-bold">New analysis</h1>
        <ol className="flex gap-2 mt-3 text-sm" aria-label="Steps">{['Subject', 'Upload', 'Sessions', 'Processing'].map((t, i) => <li key={t} aria-current={step === i + 1 ? 'step' : undefined} className={`px-3 py-1 border ${step === i + 1 ? 'border-orange text-orange' : i + 1 < step ? 'border-line' : 'border-line/50 text-neutral-600'}`}>{i + 1}. {t}</li>)}</ol></div>
      {err && <ErrorBox message={err} />}

      {step === 1 && (
        <form className="panel p-5 grid gap-4 md:grid-cols-3" onSubmit={(e) => { e.preventDefault(); if (valid) setStep(2) }}>
          <div className="md:col-span-3"><h2 className="font-semibold">Subject information</h2></div>
          <div><label className="label" htmlFor="n">Subject name</label><input id="n" className="field" required value={s.name} onChange={set('name')} /></div>
          <div><label className="label" htmlFor="a">Age (years)</label><input id="a" className="field" type="number" min={1} max={120} required value={s.age} onChange={set('age')} /></div>
          <div><label className="label" htmlFor="g">Gender</label><select id="g" className="field" value={s.gender} onChange={set('gender')}><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></select></div>
          <div><label className="label" htmlFor="h">Height (cm)</label><input id="h" className="field" type="number" value={s.height_cm} onChange={set('height_cm')} /></div>
          <div><label className="label" htmlFor="w">Weight (kg)</label><input id="w" className="field" type="number" value={s.weight_kg} onChange={set('weight_kg')} /></div>
          <div><label className="label" htmlFor="r">Resting HR (bpm)</label><input id="r" className="field" type="number" value={s.resting_hr} onChange={set('resting_hr')} /></div>
          <div><label className="label" htmlFor="m">Measured maximum HR (optional)</label><input id="m" className="field" type="number" value={s.max_hr} onChange={set('max_hr')} /></div>
          <div><label className="label" htmlFor="f">Fitness level (optional)</label><input id="f" className="field" value={s.fitness_level} onChange={set('fitness_level')} /></div>
          <div><label className="label" htmlFor="t">Activity type (optional)</label><input id="t" className="field" value={s.activity_type} onChange={set('activity_type')} /></div>
          <div><label className="label" htmlFor="d">Exercise duration, min (optional)</label><input id="d" className="field" type="number" value={s.exercise_duration_min} onChange={set('exercise_duration_min')} /></div>
          <div className="md:col-span-2"><label className="label" htmlFor="no">Notes (optional)</label><textarea id="no" className="field" rows={2} value={s.notes} onChange={set('notes')} /></div>
          <div className="grid grid-cols-2 gap-3"><MetricCard label="BMI" value={b?.value ?? null} tip="BMI = weight / height². A screening ratio, not a diagnostic tool." /><MetricCard label="BMI category" value={b?.category ?? null} /></div>
          <div className="md:col-span-3 flex justify-end"><button className="btn-primary" disabled={!valid}>Continue to upload</button></div>
        </form>)}

      {step === 2 && (<div className="space-y-3"><UploadDropzone onFile={onFile} busy={busy} progress={pct} />
        <p className="text-xs text-muted">The original file is stored unchanged; all derived data is saved separately. Your recordings are only visible to your account.</p>
        <button className="btn-ghost" onClick={() => setStep(1)}>Back</button></div>)}

      {step === 3 && up && (
        <div className="space-y-4">
          <div className="grid gap-3 grid-cols-2 md:grid-cols-5">
            <MetricCard label="File" value={up.filename} hint={`${(up.size / 1048576).toFixed(1)} MB · validated`} />
            <MetricCard label="Sessions detected" value={String(up.summary.sessions)} />
            <MetricCard label="With ECG" value={String(up.summary.with_ecg)} />
            <MetricCard label="With HR / summary" value={`${up.summary.with_hr} / ${up.summary.with_summary}`} />
            <MetricCard label="With movement" value={String(up.summary.with_movement)} />
          </div>
          <div className="flex items-center gap-3 text-sm">
            <button className="btn-ghost" onClick={() => setSel(new Set(up.sessions.map((x) => x.key)))}>Select entire dataset</button>
            <button className="btn-ghost" onClick={() => setSel(new Set())}>Clear</button><span className="text-muted">{sel.size} selected</span></div>
          <div className="grid gap-3 md:grid-cols-2">{up.sessions.map((x) => <SessionOption key={x.key} x={x} checked={sel.has(x.key)} onToggle={() => toggle(x.key)} />)}</div>
          <div className="flex justify-between"><button className="btn-ghost" onClick={() => setStep(2)}>Upload a different file</button>
            <button className="btn-primary" disabled={!sel.size} onClick={start}>Analyse {sel.size} session{sel.size === 1 ? '' : 's'}</button></div>
        </div>)}

      {step === 4 && (
        <div className="panel p-5 space-y-4"><h2 className="font-semibold">{job?.status === 'complete' ? 'Analysis complete' : job?.status === 'error' ? 'Analysis failed' : 'Analysing your recording'}</h2>
          {job?.status === 'error' && <ErrorBox message={job.error || 'Analysis failed.'} />}
          <div className="h-1.5 bg-line"><div className="h-full bg-orange transition-all" style={{ width: `${Math.round((job?.progress ?? 0) * 100)}%` }} /></div>
          <ProgressStepper steps={job?.steps || ['Uploading']} current={job?.stepIndex ?? 0} failed={job?.status === 'error'} />
          {job?.status === 'error' && <button className="btn-ghost" onClick={() => setStep(3)}>Back to session selection</button>}
        </div>)}
    </div>
  )
}

function SessionOption({ x, checked, onToggle }: { x: DetectedSession; checked: boolean; onToggle: () => void }) {
  const a = x.availability; const yn = (v: boolean) => (v ? 'Available' : 'Not available')
  return (
    <label className={`panel p-4 cursor-pointer block ${checked ? 'border-orange' : ''}`}>
      <div className="flex items-start gap-3"><input type="checkbox" className="mt-1" checked={checked} onChange={onToggle} />
        <div className="min-w-0 flex-1">
          <div className="font-semibold">{fmtDate(x.start)} <span className="text-muted font-normal text-sm">· {x.name}</span></div>
          <div className="text-sm text-muted mt-1">ECG: {yn(a.ecg)} · HR: {yn(a.hr)} · Movement: {yn(a.movement)} · Summary: {yn(a.summary)}</div>
          <dl className="grid grid-cols-3 gap-2 text-xs mt-3 readout">
            <div><dt className="text-muted font-sans">Duration</dt><dd>{fmtDuration(x.duration_s)}</dd></div>
            <div><dt className="text-muted font-sans">ECG rate</dt><dd>{x.ecg_fs_hz ? `${fmt(x.ecg_fs_hz, 0)} Hz` : 'N/A'}</dd></div>
            <div><dt className="text-muted font-sans">ECG samples</dt><dd>{x.ecg_samples.toLocaleString()}</dd></div>
            <div><dt className="text-muted font-sans">Missing</dt><dd>{x.missing_samples}</dd></div>
            <div><dt className="text-muted font-sans">Duplicates</dt><dd>{x.duplicate_samples}</dd></div>
            <div><dt className="text-muted font-sans">Signal gaps</dt><dd>{x.gaps.length}</dd></div>
          </dl>
          {x.warnings.slice(0, 2).map((w, i) => <div key={i} className="mt-2"><WarningBanner w={{ code: 'P', level: 'info', message: w }} /></div>)}
        </div></div>
    </label>
  )
}
