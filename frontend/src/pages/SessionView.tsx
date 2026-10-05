import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../services/api'
import type { Analysis, EcgWindow, HrSeries, RR } from '../types'
import { ChartCard, ChartToolbar, DataTable, ErrorBox, ExportMenu, MetricCard, SignalQualityBadge, Spinner } from '../components/ui'
import { EChart } from '../charts/EChart'
import { ecgOption } from '../charts/options'
import { useJob } from '../hooks/useJob'
import { fmt, fmtDate, fmtDuration, median, NA } from '../utils/format'
import { FrequencyPanel, HrChart, Interpretation, MovementChart, Nonlinear, PointPlot, QualityPanel, RrChart, SourceCalc, TIPS, TimeDomain, Warnings, ZonePanel, ZoneTimeline } from './Panels'
import { psdOption, zoneStackOption } from '../charts/options'

const TABS: [string, string][] = [['overview', 'Overview'], ['ecg', 'ECG'], ['rr', 'RR intervals'], ['hr', 'HR'], ['hrv', 'HRV'], ['frequency', 'Frequency'], ['training', 'Training'], ['movement', 'Movement'], ['report', 'Report']]

interface Data { a: Analysis; hr: HrSeries; rr: RR; mv: { movement: Record<string, any>; t?: number[]; v?: number[] } }

export default function SessionView() {
  const { id = '', '*': sub } = useParams(); const nav = useNavigate()
  const tab = sub || 'overview'
  const [d, setD] = useState<Data | null>(null); const [err, setErr] = useState(''); const [jobId, setJobId] = useState<string | null>(null)
  const { job } = useJob(jobId)
  const load = useCallback(() => {
    Promise.all([api.analysis(id), api.hr(id), api.rr(id), api.movement(id)]).then(([a, hr, rr, mv]) => setD({ a, hr, rr, mv })).catch((e) => setErr(e.message))
  }, [id])
  useEffect(() => { setD(null); setErr(''); load() }, [load])
  useEffect(() => { if (job?.status === 'complete') { setJobId(null); load() } }, [job?.status, load])

  if (err) return <div className="space-y-3"><ErrorBox message={err} /><Link className="text-orange" to="/app/sessions">Back to sessions</Link></div>
  if (!d) return <Spinner label="Loading analysis" />
  const { a, hr, rr, mv } = d
  const s = a.subject, rec = a.analysis.recording, q = a.analysis.quality
  const t = a.hrv.time || {}, f = a.hrv.frequency || {}, tr = a.training_results.training || {}, mov = a.movement_results.movement || {}
  const hrs = a.hr_series_stats
  const zones = a.training_results.zones?.zones
  const tl = tr.source?.training_load ?? tr.calculated?.trimp
  const ml = mov.source?.movement_load ?? mov.calculated?.load

  return (
    <div className="space-y-5">
      <header className="panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><h1 className="text-2xl font-bold">{s.name}</h1>
            <p className="text-sm text-muted mt-1">Session {a.session.sessionName} · {fmtDate(rec.start_time)} · {fmtDuration(rec.session_duration_s ?? rec.ecg_valid_duration_s)}</p>
            <p className="text-sm mt-2 readout">Age {fmt(s.age, 0)} · {s.gender} · {s.height_cm ? `${s.height_cm} cm` : NA} · {s.weight_kg ? `${s.weight_kg} kg` : NA}{s.bmi ? ` · BMI ${s.bmi}` : ''}</p></div>
          <div className="flex items-center gap-2"><SignalQualityBadge status={q.status} />
            <button className="btn-ghost" disabled={!!jobId} onClick={async () => setJobId((await api.reprocess(id)).job_id)}>{jobId ? `Reprocessing… ${Math.round((job?.progress ?? 0) * 100)}%` : 'Reprocess with current settings'}</button>
            <ExportMenu items={[{ label: 'PDF report', href: api.downloadUrl(id, 'report') }, { label: 'RR table (CSV)', href: api.downloadUrl(id, 'rr') }, { label: 'HR series (CSV)', href: api.downloadUrl(id, 'hr') }, { label: 'Summary (CSV)', href: api.downloadUrl(id, 'summary') }, { label: 'Full analysis (JSON)', href: api.downloadUrl(id, 'json') }]} /></div>
        </div>
      </header>
      <Warnings a={a} />
      <nav aria-label="Session sections" className="flex flex-wrap gap-px border-b border-line">
        {TABS.map(([k, label]) => <button key={k} aria-current={tab === k ? 'page' : undefined} onClick={() => nav(`/app/sessions/${id}/${k === 'overview' ? '' : k}`)}
          className={`px-4 py-2 text-sm border-b-2 ${tab === k ? 'border-orange text-orange font-semibold' : 'border-transparent text-neutral-300 hover:text-white'}`}>{label}</button>)}
      </nav>

      {tab === 'overview' && (<>
        <div className="grid gap-3 grid-cols-2 md:grid-cols-5">
          <MetricCard label="Avg HR" value={hrs.avg} unit="bpm" /><MetricCard label="Max HR" value={hrs.max} unit="bpm" /><MetricCard label="Min HR" value={hrs.min} unit="bpm" />
          <MetricCard label="RMSSD" value={t.rmssd} unit="ms" tip={TIPS.rmssd} /><MetricCard label="pNN50" value={t.pnn50} unit="%" tip={TIPS.pnn50} />
          <MetricCard label="LF" value={f.lf} unit="ms²" tip={TIPS.lf} /><MetricCard label="HF" value={f.hf} unit="ms²" tip={TIPS.hf} /><MetricCard label="LF/HF" value={f.lf_hf == null ? null : fmt(f.lf_hf, 2)} tip={TIPS.lf_hf} />
          <MetricCard label="Training load" value={tl} hint={tr.source?.training_load != null ? 'Source dataset value' : tr.calculated ? 'Calculated (Banister TRIMP)' : undefined} />
          <MetricCard label="Movement load" value={ml} hint={mov.source?.movement_load != null ? 'Source dataset value' : undefined} />
        </div>
        <HrChart hr={hr} zones={zones} />
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="HR zone distribution">{zones?.length ? <EChart option={zoneStackOption(zones)} height={160} label="HR zone distribution" /> : <p className="p-6 text-muted">N/A — age or HRmax needed.</p>}</ChartCard>
          <RrChart rr={rr} mean={t.mean_rr} />
          <ChartCard title="HRV power spectrum">{f.psd ? <EChart option={psdOption(f.psd, f.bands)} height={260} label="HRV power spectrum" /> : <p className="p-6 text-muted">N/A — insufficient valid data.</p>}</ChartCard>
          <MovementChart t={mv.t} v={mv.v} />
        </div>
        <PointPlot rr={rr} />
      </>)}

      {tab === 'ecg' && <EcgTab id={id} rr={rr} />}

      {tab === 'rr' && (<div className="space-y-4"><RrChart rr={rr} mean={t.mean_rr} />
        <div className="grid gap-3 grid-cols-2 md:grid-cols-4"><MetricCard label="Mean RR" value={t.mean_rr} unit="ms" /><MetricCard label="SDNN" value={t.sdnn} unit="ms" tip={TIPS.sdnn} /><MetricCard label="RMSSD" value={t.rmssd} unit="ms" tip={TIPS.rmssd} /><MetricCard label="Mean HR (ECG)" value={t.mean_hr} unit="bpm" /></div>
        <ChartCard title="RR interval table" subtitle="Original and corrected values with beat status"><RrTable rr={rr} start={rec.ecg_start_time} /></ChartCard></div>)}

      {tab === 'hr' && (<div className="space-y-4">
        <div className="grid gap-3 grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard label="Average HR" value={hrs.avg} unit="bpm" hint="Mean of the HR series" /><MetricCard label="Max HR" value={hrs.max} unit="bpm" hint="Highest value in this session" /><MetricCard label="Min HR" value={hrs.min} unit="bpm" hint="Lowest value in this session" />
          <MetricCard label="Median HR" value={hrs.median} unit="bpm" /><MetricCard label="Resting HR" value={a.analysis.hr_calc.resting_hr} unit="bpm" hint="As entered" /><MetricCard label="Theoretical HRmax" value={a.analysis.hr_calc.theoretical_hrmax} unit="bpm" hint="Age-based estimate, not measured" />
        </div>
        <HrChart hr={hr} zones={zones} /><ZonePanel zones={zones} source={a.training_results.source_zone_durations_s} /><ZoneTimeline hr={hr} zones={zones} />
        <HrMath a={a} />
        <div><h2 className="font-semibold mb-2">Source vs application-calculated</h2><div className="grid gap-3 md:grid-cols-3">
          {(['avg_hr', 'max_hr', 'min_hr'] as const).map((k) => <SourceCalc key={k} label={{ avg_hr: 'Average HR', max_hr: 'Max HR', min_hr: 'Min HR' }[k]} unit="bpm" source={a.analysis.source_vs_calculated[k]?.source} calc={a.analysis.source_vs_calculated[k]?.calculated ?? hrs[k.replace('_hr', '') === 'avg' ? 'avg' : k.replace('_hr', '')]} />)}</div></div></div>)}

      {tab === 'hrv' && (<div className="space-y-6">
        <Section n="A" t="Recording overview"><p className="text-sm text-neutral-300">Valid ECG {fmtDuration(rec.ecg_valid_duration_s)} ({rec.ecg_duration_class || NA}); session {fmtDuration(rec.session_duration_s)}. {rec.ecg_valid_duration_s && rec.ecg_valid_duration_s < 300 ? 'This is ultra-short-term HRV: use it as an approximate snapshot, not a long-term measure.' : ''}</p></Section>
        <Section n="B" t="Signal quality"><QualityPanel a={a} /></Section>
        <Section n="C" t="RR intervals"><RrChart rr={rr} mean={t.mean_rr} /></Section>
        <Section n="D" t="Time domain"><TimeDomain a={a} /></Section>
        <Section n="E" t="Frequency domain"><FrequencyPanel a={a} /></Section>
        <Section n="F" t="Nonlinear (Poincaré)"><Nonlinear a={a} /><div className="mt-3"><PointPlot rr={rr} /></div></Section>
        <Section n="G" t="Interpretation"><Interpretation a={a} /></Section></div>)}

      {tab === 'frequency' && <FrequencyPanel a={a} />}

      {tab === 'training' && (<div className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2">
          <SourceCalc label="Training load" unit="Calculated = Banister TRIMP; not the same scale as the device value" source={tr.source?.training_load} calc={tr.calculated?.trimp} />
          <SourceCalc label="Training intensity" source={tr.source?.training_intensity} calc={tr.calculated?.intensity} nd={3} /></div>
        <div className="grid gap-3 grid-cols-2 md:grid-cols-4"><MetricCard label="Session duration" value={fmtDuration(rec.session_duration_s)} /><MetricCard label="Average HR" value={hrs.avg} unit="bpm" /><MetricCard label="HRmax used (estimate)" value={a.analysis.hr_calc.hrmax_used_for_zones} unit="bpm" /><MetricCard label="Resting HR" value={a.analysis.hr_calc.resting_hr} unit="bpm" /></div>
        <p className="text-xs text-muted">Calculated load: {tr.calculated?.formula || 'N/A (needs age/HRmax and resting HR)'}. It does not replicate any proprietary algorithm.</p>
        <ZonePanel zones={zones} source={a.training_results.source_zone_durations_s} /></div>)}

      {tab === 'movement' && (<div className="space-y-4">
        {!mov.available && <p className="panel p-6">Movement data not available for this session.</p>}
        <div className="grid gap-3 md:grid-cols-2"><SourceCalc label="Movement load" source={mov.source?.movement_load} calc={mov.calculated?.load} nd={3} unit="acc RMS-hours" /><SourceCalc label="Movement intensity" source={mov.source?.movement_intensity} calc={mov.calculated?.intensity} nd={3} unit="mean acc RMS" /></div>
        <MovementChart t={mv.t} v={mv.v} /><p className="text-xs text-muted">{mov.calculated?.algorithm}</p></div>)}

      {tab === 'report' && (<div className="space-y-5">
        <div className="panel p-4 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold">ECG / HRV analysis report</h2><p className="text-sm text-muted">{s.name} · {fmtDate(rec.start_time)}</p></div>
          <div className="flex gap-2"><a className="btn-primary" href={api.downloadUrl(id, 'report')}>Download PDF</a><a className="btn-ghost" href={api.downloadUrl(id, 'rr')}>CSV</a><a className="btn-ghost" href={api.downloadUrl(id, 'json')}>JSON</a></div></div>
        <Section n="1" t="Signal quality"><QualityPanel a={a} /></Section><Section n="2" t="Heart rate summary"><HrChart hr={hr} zones={zones} /></Section>
        <Section n="3" t="HR zones"><ZonePanel zones={zones} source={a.training_results.source_zone_durations_s} /></Section><Section n="4" t="Time-domain HRV"><TimeDomain a={a} /></Section>
        <Section n="5" t="Frequency-domain HRV"><FrequencyPanel a={a} /></Section><Section n="6" t="Interpretation"><Interpretation a={a} /></Section>
        <Section n="7" t="Processing parameters"><pre className="panel p-3 text-xs overflow-auto text-neutral-300">{JSON.stringify(a.analysis.parameters, null, 1)}</pre></Section>
        <Section n="8" t="Limitations"><ul className="list-disc pl-5 text-sm text-neutral-300 space-y-1"><li>ECG in this export format is stored in intermittent snapshots; HRV reflects only the valid ECG windows.</li><li>Ultra-short recordings give approximate HRV; VLF and total power are withheld below 5 minutes.</li><li>Exercise changes HR and HRV strongly; do not compare with resting recordings.</li><li>This is not a medical device and makes no diagnosis.</li></ul></Section></div>)}
    </div>
  )
}

function Section({ n, t, children }: { n: string; t: string; children: ReactNode }) {
  return <section aria-label={t}><h2 className="font-semibold text-lg mb-2"><span className="text-orange mr-2">{n}</span>{t}</h2>{children}</section>
}

function HrMath({ a }: { a: Analysis }) {
  const c = a.analysis.hr_calc; const [pct, setPct] = useState(70)
  const target = c.resting_hr != null && c.hrmax_used_for_zones ? c.resting_hr + (pct / 100) * (c.hrmax_used_for_zones - c.resting_hr) : null
  return (
    <ChartCard title="Heart rate calculations" subtitle="All values below are estimates, not measurements">
      <div className="grid gap-3 grid-cols-2 md:grid-cols-6">
        <MetricCard label="Age" value={c.age} unit="y" /><MetricCard label="Resting HR" value={c.resting_hr} unit="bpm" /><MetricCard label="Theoretical HRmax" value={c.theoretical_hrmax} unit="bpm" hint={`Formula: ${c.hrmax_formula}`} />
        <MetricCard label="HR reserve" value={c.hr_reserve} unit="bpm" hint="HRmax − HRrest" /><MetricCard label="BMI" value={c.bmi} hint="Not a diagnostic tool" />
        <div className="panel p-4"><label className="text-sm text-muted" htmlFor="int">Karvonen intensity</label>
          <select id="int" className="field mt-1" value={pct} onChange={(e) => setPct(Number(e.target.value))}>{[50, 60, 70, 80, 90].map((p) => <option key={p} value={p}>{p}%</option>)}</select>
          <div className="readout text-2xl mt-2">{target == null ? NA : fmt(target, 0)}<span className="text-sm text-orange font-sans ml-1">bpm</span></div></div>
      </div><p className="text-xs text-muted mt-2">Target HR = HRrest + intensity × HRR. Age-based HRmax is a population estimate and may differ markedly from an individual's measured maximum.</p>
    </ChartCard>
  )
}

function RrTable({ rr, start }: { rr: RR; start?: string }) {
  const rows = (rr.t_s || []).map((t, i) => ({ i, t, rr: rr.rr_ms?.[i], hr: rr.hr_bpm?.[i], status: rr.status?.[i], art: rr.artifact?.[i], reason: rr.reason?.[i], c: rr.rr_corrected_ms?.[i] }))
  const base = start ? new Date(start).getTime() : null
  return (
    <DataTable rows={rows} rowKey={(r) => String(r.i)} maxHeight={360} empty="N/A — no RR intervals."
      cols={[{ key: 't', head: 'Timestamp', render: (r) => base ? new Date(base + r.t * 1000).toISOString().slice(11, 23) : `${r.t.toFixed(3)} s` },
        { key: 'r', head: 'RR (ms)', align: 'right', render: (r) => fmt(r.rr, 1) }, { key: 'h', head: 'HR (bpm)', align: 'right', render: (r) => fmt(r.hr, 1) },
        { key: 's', head: 'Beat status', render: (r) => r.status }, { key: 'a', head: 'Artifact status', render: (r) => (r.art ? `Flagged (${r.reason})` : 'None') },
        { key: 'c', head: 'Corrected RR (ms)', align: 'right', render: (r) => fmt(r.c, 1) }]} />
  )
}

function EcgTab({ id, rr }: { id: string; rr: RR }) {
  const [w, setW] = useState<EcgWindow | null>(null); const [err, setErr] = useState(''); const [range, setRange] = useState<[number, number] | null>(null)
  const fetchWin = useCallback((r: [number, number] | null) => { setErr(''); api.ecg(id, r?.[0], r?.[1]).then((x) => { setW(x); if (!r) setRange([x.t_min, x.t_max]) }).catch((e) => setErr(e.message)) }, [id])
  useEffect(() => { fetchWin(null) }, [fetchWin])
  if (err) return <ErrorBox message={err.includes('404') || err.includes('No ECG') ? 'No ECG data for this session.' : err} />
  if (!w || !range) return <Spinner label="Loading ECG" />
  const [lo, hi] = range; const span = hi - lo; const mid = (lo + hi) / 2
  const go = (a: number, b: number) => { const r: [number, number] = [Math.max(w.t_min, a), Math.min(w.t_max, b)]; setRange(r); fetchWin(r) }
  const inWin = (rr.t_s || []).map((t, i) => ({ t, v: rr.rr_ms?.[i] })).filter((x) => x.t >= lo && x.t <= hi && x.v != null).map((x) => x.v as number)
  return (
    <div className="space-y-4">
      <ChartCard title="ECG waveform with R-peaks" subtitle={`${w.n_window.toLocaleString()} samples in view${w.downsampled ? ' — min/max downsampled for display; analysis uses full resolution' : ''}`}
        actions={<ChartToolbar>
          <button className="btn-ghost py-1" onClick={() => go(mid - span, mid + span)}>Zoom out</button>
          <button className="btn-ghost py-1" onClick={() => go(mid - span / 4, mid + span / 4)}>Zoom in</button>
          <button className="btn-ghost py-1" onClick={() => go(lo - span / 2, hi - span / 2)} aria-label="Pan left">◀</button>
          <button className="btn-ghost py-1" onClick={() => go(lo + span / 2, hi + span / 2)} aria-label="Pan right">▶</button>
          <button className="btn-ghost py-1" onClick={() => go(w.t_min, w.t_max)}>Reset</button></ChartToolbar>}>
        <EChart option={ecgOption(w)} height={340} label="ECG waveform with R-peak markers" />
        <div className="flex flex-wrap gap-2 mt-3 text-sm"><span className="text-muted self-center">Segments:</span>{w.segments.map((s) => <button key={s.segment} className="btn-ghost py-1" onClick={() => go(s.start, s.end)}>#{s.segment + 1} · {fmtDuration(s.end - s.start)}</button>)}</div>
      </ChartCard>
      <div className="grid gap-3 grid-cols-2 md:grid-cols-5">
        <MetricCard label="R-peaks in view" value={String(w.peaks_t.length)} /><MetricCard label="Average RR" value={inWin.length ? inWin.reduce((a, b) => a + b, 0) / inWin.length : null} unit="ms" />
        <MetricCard label="Median RR" value={median(inWin)} unit="ms" /><MetricCard label="Min RR" value={inWin.length ? Math.min(...inWin) : null} unit="ms" /><MetricCard label="Max RR" value={inWin.length ? Math.max(...inWin) : null} unit="ms" />
      </div>
    </div>
  )
}
