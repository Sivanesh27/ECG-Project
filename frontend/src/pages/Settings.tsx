import { useEffect, useState } from 'react'
import { api } from '../services/api'
import type { AppSettings } from '../types'
import { ErrorBox, Spinner } from '../components/ui'

export default function Settings() {
  const [s, setS] = useState<AppSettings | null>(null); const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  useEffect(() => { api.settings().then(setS).catch((e) => setErr(e.message)) }, [])
  if (err && !s) return <ErrorBox message={err} />
  if (!s) return <Spinner />
  const art = s.artifact, flt = s.filter, fq = s.freq
  const patch = (p: Partial<AppSettings>) => setS({ ...s, ...p })
  const save = async () => { setErr(''); setMsg(''); try { setS(await api.saveSettings(s)); setMsg('Settings saved. They apply to new analyses; use “Reprocess” on a session to apply them to existing data.') } catch (e: any) { setErr(e.message) } }
  const zoneSet = (i: number, j: 0 | 1, v: number) => patch({ zones: s.zones.map((z, k) => (k === i ? (j === 0 ? [v / 100, z[1]] : [z[0], v / 100]) : z)) })
  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-3xl font-bold">Settings</h1>
      {err && <ErrorBox message={err} />}{msg && <p role="status" className="border border-green-800 text-green-300 px-3 py-2 text-sm">{msg}</p>}
      <section className="panel p-5 space-y-3"><h2 className="font-semibold">Heart rate</h2>
        <div className="grid gap-4 md:grid-cols-2"><div><label className="label" htmlFor="f">HRmax formula (theoretical)</label>
          <select id="f" className="field" value={s.hrmax_formula} onChange={(e) => patch({ hrmax_formula: e.target.value as AppSettings['hrmax_formula'] })}><option value="220-age">220 − age</option><option value="208-0.7age">208 − 0.7 × age</option><option value="custom">Custom value</option></select></div>
          {s.hrmax_formula === 'custom' && <div><label className="label" htmlFor="c">Custom HRmax (bpm)</label><input id="c" type="number" className="field" value={s.hrmax_custom ?? ''} onChange={(e) => patch({ hrmax_custom: e.target.value ? Number(e.target.value) : null })} /></div>}</div>
        <fieldset><legend className="label">HR zones (% of HRmax)</legend><div className="grid gap-2 md:grid-cols-5">{s.zones.map((z, i) => <div key={i} className="flex items-center gap-1 text-sm">Z{i + 1}<input aria-label={`Zone ${i + 1} lower %`} type="number" className="field px-2" value={Math.round(z[0] * 100)} onChange={(e) => zoneSet(i, 0, Number(e.target.value))} />–<input aria-label={`Zone ${i + 1} upper %`} type="number" className="field px-2" value={Math.round(z[1] * 100)} onChange={(e) => zoneSet(i, 1, Number(e.target.value))} /></div>)}</div>
          <button className="btn-ghost mt-2" onClick={() => patch({ zones: [[0.5, 0.6], [0.6, 0.7], [0.7, 0.8], [0.8, 0.9], [0.9, 1.0]] })}>Restore default 5 zones</button></fieldset></section>
      <section className="panel p-5 grid gap-4 md:grid-cols-3"><h2 className="font-semibold md:col-span-3">ECG processing</h2>
        <div><label className="label" htmlFor="p">Powerline frequency</label><select id="p" className="field" value={s.powerline_hz} onChange={(e) => patch({ powerline_hz: Number(e.target.value) as 50 | 60 })}><option value={50}>50 Hz (India, default)</option><option value={60}>60 Hz</option></select></div>
        <div><label className="label" htmlFor="lo">Band-pass low (Hz)</label><input id="lo" type="number" step="0.1" className="field" placeholder="0.5" value={flt.low_hz ?? ''} onChange={(e) => patch({ filter: { ...flt, low_hz: e.target.value ? Number(e.target.value) : undefined } })} /></div>
        <div><label className="label" htmlFor="hi">Band-pass high (Hz)</label><input id="hi" type="number" step="1" className="field" placeholder="40" value={flt.high_hz ?? ''} onChange={(e) => patch({ filter: { ...flt, high_hz: e.target.value ? Number(e.target.value) : undefined } })} /></div>
        <div><label className="label" htmlFor="sr">Sampling-rate override (Hz)</label><input id="sr" type="number" className="field" placeholder="auto-detect" value={s.sampling_rate_override ?? ''} onChange={(e) => patch({ sampling_rate_override: e.target.value ? Number(e.target.value) : null })} />
          <p className="text-xs text-muted mt-1">Only used when the rate cannot be estimated from the file (e.g. a single ECG chunk).</p></div></section>
      <section className="panel p-5 grid gap-4 md:grid-cols-3"><h2 className="font-semibold md:col-span-3">Artifacts and spectral analysis</h2>
        <div><label className="label" htmlFor="am">Artifact handling</label><select id="am" className="field" value={art.mode ?? 'interpolate'} onChange={(e) => patch({ artifact: { ...art, mode: e.target.value } })}><option value="interpolate">Interpolate (default)</option><option value="reject">Reject</option><option value="keep">Keep raw</option></select></div>
        <div><label className="label" htmlFor="mn">Min RR (ms)</label><input id="mn" type="number" className="field" placeholder="300" value={art.min_rr_ms ?? ''} onChange={(e) => patch({ artifact: { ...art, min_rr_ms: e.target.value ? Number(e.target.value) : undefined } })} /></div>
        <div><label className="label" htmlFor="mx">Max RR (ms)</label><input id="mx" type="number" className="field" placeholder="2000" value={art.max_rr_ms ?? ''} onChange={(e) => patch({ artifact: { ...art, max_rr_ms: e.target.value ? Number(e.target.value) : undefined } })} /></div>
        <div><label className="label" htmlFor="fm">Frequency-domain method</label><select id="fm" className="field" value={fq.method ?? 'welch'} onChange={(e) => patch({ freq: { ...fq, method: e.target.value } })}><option value="welch">Welch (resampled)</option><option value="lomb">Lomb–Scargle (uneven)</option></select></div>
        <div><label className="label" htmlFor="rs">Resample rate (Hz)</label><input id="rs" type="number" className="field" placeholder="4" value={fq.resample_hz ?? ''} onChange={(e) => patch({ freq: { ...fq, resample_hz: e.target.value ? Number(e.target.value) : undefined } })} /></div>
        <div><label className="label" htmlFor="ws">Welch window (s)</label><input id="ws" type="number" className="field" placeholder="120" value={fq.welch_window_s ?? ''} onChange={(e) => patch({ freq: { ...fq, welch_window_s: e.target.value ? Number(e.target.value) : undefined } })} /></div></section>
      <button className="btn-primary" onClick={save}>Save settings</button>
    </div>
  )
}
