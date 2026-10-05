import { useMemo, useState } from 'react'
import type { Analysis, HrSeries, RR, Zone } from '../types'
import { ChartCard, DataTable, InfoTooltip, MetricCard, WarningBanner, ZoneBadge } from '../components/ui'
import { EChart } from '../charts/EChart'
import { hrOption, movementOption, POINT_MODES, pointOption, psdOption, rrOption, zoneDonutOption, zoneStackOption, zoneTimelineOption, type PointX } from '../charts/options'
import { fmt, fmtDuration, NA } from '../utils/format'

export const TIPS: Record<string, string> = {
  rmssd: 'Root mean square of successive differences between adjacent normal-to-normal intervals. Unit: ms.',
  sdnn: 'Standard deviation of normal-to-normal intervals. Interpretation depends strongly on recording duration.',
  sdsd: 'Standard deviation of successive NN differences. Unit: ms.',
  pnn50: 'Percentage of successive NN differences larger than 50 ms.', pnn20: 'Percentage of successive NN differences larger than 20 ms.',
  nn50: 'Number of successive NN differences larger than 50 ms.', nn20: 'Number of successive NN differences larger than 20 ms.',
  vlf: 'Power in the 0.0033–0.04 Hz band. Needs long recordings (≥ 5 min here); not reported otherwise.',
  lf: 'Power in the 0.04–0.15 Hz frequency band.', hf: 'Power in the 0.15–0.40 Hz frequency band.',
  lf_hf: 'Ratio of LF power to HF power. This ratio should not be interpreted as a direct measure of sympathetic/parasympathetic balance.',
  total: 'VLF + LF + HF power. Only reported when VLF can be reported.',
}
const DIFF_TIP = 'Source and calculated values can differ because the device and this application use different preprocessing and quality filtering.'

export function SourceCalc({ label, unit, source, calc, nd = 2 }: { label: string; unit?: string; source?: number | null; calc?: number | null; nd?: number }) {
  const diff = source != null && calc != null ? calc - source : null
  return (
    <div className="panel p-4">
      <div className="text-sm text-muted">{label}</div>
      <dl className="mt-2 grid grid-cols-3 gap-2 readout text-sm">
        <div><dt className="text-xs text-muted font-sans">Source dataset</dt><dd className="text-lg">{fmt(source, nd)}</dd></div>
        <div><dt className="text-xs text-muted font-sans">Application calculated</dt><dd className="text-lg text-orange">{fmt(calc, nd)}</dd></div>
        <div><dt className="text-xs text-muted font-sans">Difference <InfoTooltip text={DIFF_TIP} /></dt><dd className="text-lg">{diff == null ? NA : (diff > 0 ? '+' : '') + fmt(diff, nd)}</dd></div>
      </dl>{unit && <p className="text-xs text-muted mt-1">{unit}</p>}
    </div>
  )
}

export function Warnings({ a }: { a: Analysis }) {
  const w = a.analysis.warnings || []
  if (!w.length) return null
  return <div className="space-y-2">{w.filter((x) => x.level !== 'info' || true).map((x, i) => <WarningBanner key={i} w={x} />)}</div>
}

export function QualityPanel({ a }: { a: Analysis }) {
  const q = a.analysis.quality, r = a.analysis.recording
  return (
    <div className="grid gap-3 grid-cols-2 md:grid-cols-4 xl:grid-cols-6">
      <MetricCard label="ECG duration (valid)" value={r.ecg_valid_duration_s ? fmtDuration(r.ecg_valid_duration_s) : null} hint={r.ecg_duration_class ? `Length class: ${r.ecg_duration_class}` : undefined} />
      <MetricCard label="Sampling rate" value={r.ecg_fs_hz} unit="Hz" hint={r.fs_source} />
      <MetricCard label="ECG samples" value={r.ecg_samples ? r.ecg_samples.toLocaleString() : null} />
      <MetricCard label="R-peaks detected" value={q.n_peaks ? String(q.n_peaks) : null} />
      <MetricCard label="Accepted beats" value={q.n_rr ? String(q.accepted_beats) : null} />
      <MetricCard label="Rejected / corrected" value={q.n_rr ? `${q.rejected_beats} / ${q.interpolated_beats}` : null} />
      <MetricCard label="Artifact rate" value={q.artifact_pct} unit="%" />
      <MetricCard label="Signal quality" value={q.signal_quality_pct} unit="%" sub={<span className="font-semibold">{q.status}</span>} />
      <MetricCard label="Missing samples" value={String(q.missing_samples ?? 0)} />
      <MetricCard label="Duplicate timestamps" value={String(q.duplicate_samples ?? 0)} />
      <MetricCard label="Signal gaps" value={String((q.gaps || []).length)} />
      <MetricCard label="Device HR quality" value={q.device_hr_quality_mean} hint="Mean of source hr_quality" />
    </div>
  )
}

export function TimeDomain({ a }: { a: Analysis }) {
  const t = a.hrv.time || {}
  return (
    <div className="grid gap-3 grid-cols-2 md:grid-cols-4">
      <MetricCard label="SDNN" value={t.sdnn} unit="ms" tip={TIPS.sdnn} /><MetricCard label="RMSSD" value={t.rmssd} unit="ms" tip={TIPS.rmssd} />
      <MetricCard label="SDSD" value={t.sdsd} unit="ms" tip={TIPS.sdsd} /><MetricCard label="CVNN" value={t.cvnn} unit="%" />
      <MetricCard label="pNN50" value={t.pnn50} unit="%" tip={TIPS.pnn50} /><MetricCard label="pNN20" value={t.pnn20} unit="%" tip={TIPS.pnn20} />
      <MetricCard label="NN50" value={t.nn50 == null ? null : String(t.nn50)} tip={TIPS.nn50} /><MetricCard label="NN20" value={t.nn20 == null ? null : String(t.nn20)} tip={TIPS.nn20} />
      <MetricCard label="Mean RR" value={t.mean_rr} unit="ms" /><MetricCard label="Median RR" value={t.median_rr} unit="ms" />
      <MetricCard label="Min / max RR" value={t.min_rr == null ? null : `${fmt(t.min_rr, 0)} / ${fmt(t.max_rr, 0)}`} unit="ms" /><MetricCard label="HRV triangular index" value={t.hrv_triangular_index} hint="Needs ≥ 200 NN" />
    </div>
  )
}

export function FrequencyPanel({ a }: { a: Analysis }) {
  const f = a.hrv.frequency || {}
  const bands = (f.bands || { vlf: [0.0033, 0.04], lf: [0.04, 0.15], hf: [0.15, 0.4] }) as Record<string, [number, number]>
  return (
    <div className="space-y-4">
      {(f.notes || []).map((n: string, i: number) => <WarningBanner key={i} w={{ code: 'F', level: 'info', message: n }} />)}
      <div className="grid gap-3 grid-cols-2 md:grid-cols-5">
        <MetricCard label="VLF" value={f.vlf} unit="ms²" tip={TIPS.vlf} /><MetricCard label="LF" value={f.lf} unit="ms²" tip={TIPS.lf} /><MetricCard label="HF" value={f.hf} unit="ms²" tip={TIPS.hf} />
        <MetricCard label="LF/HF" value={f.lf_hf == null ? null : fmt(f.lf_hf, 2)} tip={TIPS.lf_hf} /><MetricCard label="Total power" value={f.total_power} unit="ms²" tip={TIPS.total} />
      </div>
      <ChartCard title="Power spectral density" subtitle={`Method: ${f.method === 'lomb' ? 'Lomb–Scargle' : 'Welch on 4 Hz resampled tachogram'} · analysed ${fmtDuration(f.analysed_s)}`}>
        {f.psd ? <EChart option={psdOption(f.psd, bands)} height={300} label="Power spectral density with VLF, LF and HF bands" /> : <p className="p-6 text-muted">N/A — insufficient valid data for spectral analysis.</p>}
      </ChartCard>
      <DataTable rowKey={(r) => r[0]} rows={[['VLF', f.vlf, 'ms²'], ['LF', f.lf, 'ms²'], ['HF', f.hf, 'ms²'], ['LF/HF', f.lf_hf, 'ratio'], ['Total power', f.total_power, 'ms²']] as [string, number | null, string][]}
        cols={[{ key: 'm', head: 'Metric', render: (r) => r[0] }, { key: 'v', head: 'Value', align: 'right', render: (r) => fmt(r[1], r[0] === 'LF/HF' ? 2 : 1) }, { key: 'u', head: 'Unit', render: (r) => r[2] }]} />
      <p className="text-xs text-muted">LF/HF is a ratio of band powers and is not a direct measure of sympathetic/parasympathetic balance. Short windows give approximate spectral estimates.</p>
    </div>
  )
}

export function Nonlinear({ a }: { a: Analysis }) {
  const n = a.hrv.nonlinear || {}
  return <div className="grid gap-3 grid-cols-3"><MetricCard label="SD1" value={n.sd1} unit="ms" hint="Short-term (beat-to-beat) variability" /><MetricCard label="SD2" value={n.sd2} unit="ms" hint="Longer-term variability" /><MetricCard label="SD1/SD2" value={n.sd1_sd2 == null ? null : fmt(n.sd1_sd2, 2)} /></div>
}

export function Interpretation({ a }: { a: Analysis }) {
  return (
    <ul className="space-y-2">{a.interpretation.map((i, k) => (
      <li key={k} className="panel p-3 text-sm"><span className="font-semibold">{i.metric}</span>{i.value && <span className="readout text-orange"> — {i.value}</span>}<p className="text-neutral-300 mt-1">{i.text}</p></li>))}</ul>
  )
}

export function PointPlot({ rr }: { rr: RR }) {
  const [mode, setMode] = useState<PointX>('poincare')
  const opt = useMemo(() => pointOption(rr, mode), [rr, mode])
  return (
    <ChartCard title="Point-based physiological plot" subtitle="Each point is one beat interval; white diamonds are flagged outliers. Choose what to plot."
      actions={<select aria-label="Plot type" className="field w-auto" value={mode} onChange={(e) => setMode(e.target.value as PointX)}>{POINT_MODES.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}</select>}>
      {rr.t_s?.length ? <EChart option={opt} height={300} label="Point plot of RR intervals" /> : <p className="p-6 text-muted">N/A — no RR intervals for this session.</p>}
    </ChartCard>
  )
}

export function HrChart({ hr, zones }: { hr: HrSeries; zones?: Zone[] }) {
  if (!hr.t?.length) return <ChartCard title="Heart rate over time"><p className="p-6 text-muted">Heart-rate data not available for this session.</p></ChartCard>
  return <ChartCard title="Heart rate over time" subtitle={`Series: ${hr.stats?.series_source ?? 'N/A'} · drag to zoom, toolbox to reset or save`}><EChart option={hrOption(hr.t, hr.v!, zones)} height={320} label="Heart rate over time" /></ChartCard>
}

export function ZonePanel({ zones, source }: { zones?: Zone[]; source?: Record<string, number | null> | null }) {
  if (!zones?.length) return <p className="panel p-6 text-muted">N/A — HR zones need heart-rate data plus age or a measured HRmax.</p>
  return (
    <div className="space-y-3">
      <div className="grid gap-3 grid-cols-2 md:grid-cols-6">{zones.map((z) => <div key={z.zone} className="panel p-3"><ZoneBadge z={z} /><div className="readout text-2xl mt-1">{fmt(z.seconds / 60, 1)}<span className="text-sm text-orange font-sans ml-1">min</span></div><div className="text-xs text-muted">{fmt(z.percent, 1)}% · {fmt(z.lo_bpm, 0)}–{fmt(z.hi_bpm, 0)} bpm</div></div>)}</div>
      <div className="grid gap-3 lg:grid-cols-2">
        <ChartCard title="Zone distribution"><EChart option={zoneStackOption(zones)} height={150} label="Stacked bar of time in HR zones" /><EChart option={zoneDonutOption(zones)} height={230} label="Donut of time in HR zones" /></ChartCard>
        <DataTable rowKey={(z) => String(z.zone)} rows={zones} cols={[{ key: 'z', head: 'Zone', render: (z) => <ZoneBadge z={z} /> }, { key: 'r', head: '% HRmax', render: (z) => `${fmt(z.lo_pct, 0)}–${fmt(z.hi_pct, 0)}` },
          { key: 't', head: 'Time', align: 'right', render: (z) => fmtDuration(z.seconds) }, { key: 'p', head: '% session', align: 'right', render: (z) => fmt(z.percent, 1) },
          { key: 'a', head: 'Avg HR', align: 'right', render: (z) => fmt(z.avg_hr, 0) }, { key: 'k', head: 'Peak HR', align: 'right', render: (z) => fmt(z.peak_hr, 0) }]} />
      </div>
      {source && <p className="text-xs text-muted">Source dataset zone durations (its own HRmax/zone definition): {Object.entries(source).map(([k, v]) => `${k.replace('_', ' ')}: ${v == null ? NA : fmtDuration(v)}`).join(' · ')}</p>}
    </div>
  )
}

export function ZoneTimeline({ hr, zones }: { hr: HrSeries; zones?: Zone[] }) {
  if (!hr.t?.length || !zones?.length) return null
  return <ChartCard title="Zone timeline"><EChart option={zoneTimelineOption(hr.t, hr.v!, zones)} height={200} label="Heart rate coloured by zone" /></ChartCard>
}

export function RrChart({ rr, mean }: { rr: RR; mean?: number | null }) {
  if (!rr.t_s?.length) return <ChartCard title="RR tachogram"><p className="p-6 text-muted">N/A — no RR intervals (no usable ECG in this session).</p></ChartCard>
  return <ChartCard title="RR tachogram" subtitle="Normal beats, flagged beats and corrected values"><EChart option={rrOption(rr, mean)} height={300} label="RR tachogram" /></ChartCard>
}

export function MovementChart({ t, v }: { t?: number[]; v?: number[] }) {
  if (!t?.length) return <ChartCard title="Movement load vs time"><p className="p-6 text-muted">Movement data not available for this session.</p></ChartCard>
  return <ChartCard title="Movement load vs time"><EChart option={movementOption(t, v!)} height={280} label="Movement over time" /></ChartCard>
}
