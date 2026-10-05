import type { Option } from './EChart'
import type { EcgWindow, RR, Zone } from '../types'
import { ZONE_COLORS } from '../components/ui'

const ORANGE = '#FF6A00', BRIGHT = '#FF7A18', MUTED = '#A0A0A0', LINE = '#2A2A2A'
const text = { color: '#d4d4d4', fontFamily: 'Barlow, sans-serif', fontSize: 12 }
const axis = (name: string, extra: Record<string, unknown> = {}) => ({
  name, nameLocation: 'middle' as const, nameGap: 28, nameTextStyle: { color: MUTED }, axisLine: { lineStyle: { color: LINE } },
  axisLabel: { color: MUTED }, splitLine: { lineStyle: { color: '#1f1f1f' } }, ...extra,
})
const tools = { toolbox: { right: 8, top: 0, iconStyle: { borderColor: MUTED }, feature: { dataZoom: { yAxisIndex: 'none', title: { zoom: 'Zoom to region', back: 'Undo zoom' } }, restore: { title: 'Reset' }, saveAsImage: { title: 'Download image', backgroundColor: '#111111' } } } }
const zoom = [{ type: 'inside' as const }, { type: 'slider' as const, height: 18, borderColor: LINE, fillerColor: 'rgba(255,106,0,.18)', handleStyle: { color: ORANGE }, textStyle: { color: MUTED } }]
const grid = { left: 56, right: 20, top: 34, bottom: 62 }
const base = { backgroundColor: 'transparent', textStyle: text, animation: false }
const min = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`

export function hrOption(t: number[], v: number[], zones?: Zone[]): Option {
  const areas = (zones || []).filter((z) => z.zone > 0).map((z) => [{ yAxis: z.lo_bpm, itemStyle: { color: ZONE_COLORS[z.zone % 6], opacity: 0.1 } }, { yAxis: z.hi_bpm }])
  return { ...base, ...tools, grid, dataZoom: zoom, tooltip: { trigger: 'axis', formatter: (p: any) => `${min(p[0].value[0])} (mm:ss)<br/><b>${p[0].value[1].toFixed(1)}</b> bpm` },
    xAxis: { type: 'value', ...axis('Time (mm:ss)'), axisLabel: { color: MUTED, formatter: min } }, yAxis: { type: 'value', ...axis('HR (bpm)', { nameGap: 38 }), scale: true },
    series: [{ type: 'line', data: t.map((x, i) => [x, v[i]]), showSymbol: false, sampling: 'lttb', lineStyle: { color: ORANGE, width: 1.6 }, markArea: { silent: true, data: areas as any } }] }
}

export function zoneStackOption(zones: Zone[]): Option {
  return { ...base, grid: { left: 10, right: 10, top: 34, bottom: 26 }, tooltip: { trigger: 'item', formatter: (p: any) => `${p.seriesName}: ${p.value.toFixed(1)} %` }, legend: { top: 0, textStyle: { color: MUTED }, itemWidth: 10, itemHeight: 10 },
    xAxis: { type: 'value', max: 100, ...axis('% of session', { nameGap: 22 }) }, yAxis: { type: 'category', data: ['Zones'], show: false },
    series: zones.map((z) => ({ name: z.label, type: 'bar' as const, stack: 'z', data: [z.percent], itemStyle: { color: ZONE_COLORS[z.zone % 6] } })) }
}

export function zoneDonutOption(zones: Zone[]): Option {
  return { ...base, tooltip: { trigger: 'item', formatter: (p: any) => `${p.name}<br/>${(p.value / 60).toFixed(1)} min (${p.percent}%)` },
    series: [{ type: 'pie', radius: ['52%', '78%'], label: { color: '#d4d4d4', formatter: '{b}' }, itemStyle: { borderColor: '#181818', borderWidth: 2 },
      data: zones.filter((z) => z.seconds > 0).map((z) => ({ name: z.label, value: z.seconds, itemStyle: { color: ZONE_COLORS[z.zone % 6] } })) }] }
}

export function zoneTimelineOption(t: number[], v: number[], zones: Zone[]): Option {
  const pieces = zones.map((z) => ({ gte: z.zone === 0 ? 0 : z.lo_bpm, lt: z.hi_bpm, color: ZONE_COLORS[z.zone % 6] }))
  if (pieces.length) (pieces[pieces.length - 1] as any).lt = 400
  return { ...base, grid: { left: 56, right: 20, top: 14, bottom: 40 }, tooltip: { trigger: 'axis' }, visualMap: { show: false, dimension: 1, pieces },
    xAxis: { type: 'value', ...axis('Time (mm:ss)'), axisLabel: { color: MUTED, formatter: min } }, yAxis: { type: 'value', ...axis('HR (bpm)', { nameGap: 38 }), scale: true },
    series: [{ type: 'line', data: t.map((x, i) => [x, v[i]]), showSymbol: false, lineStyle: { width: 2 } }] }
}

export function rrOption(rr: RR, mean?: number | null): Option {
  const t = rr.t_s || [], v = rr.rr_ms || [], c = rr.rr_corrected_ms || [], a = rr.artifact || []
  const normal: number[][] = [], bad: number[][] = [], fixed: number[][] = []
  t.forEach((x, i) => { if (v[i] == null) return; if (a[i]) { bad.push([x, v[i] as number]); if (c[i] != null) fixed.push([x, c[i] as number]) } else normal.push([x, v[i] as number]) })
  return { ...base, ...tools, grid, dataZoom: zoom, legend: { top: 0, left: 8, textStyle: { color: MUTED } },
    tooltip: { trigger: 'item', formatter: (p: any) => `${p.seriesName}<br/>t = ${p.value[0].toFixed(2)} s<br/><b>${p.value[1].toFixed(0)}</b> ms` },
    xAxis: { type: 'value', ...axis('Time from ECG start (s)'), scale: true }, yAxis: { type: 'value', ...axis('RR interval (ms)', { nameGap: 40 }), scale: true },
    series: [
      { name: 'Normal beats', type: 'scatter', symbolSize: 5, data: normal, itemStyle: { color: ORANGE },
        markLine: mean ? { silent: true, symbol: 'none', lineStyle: { color: MUTED, type: 'dashed' }, data: [{ yAxis: mean, label: { formatter: 'mean RR', color: MUTED } }] } : undefined },
      { name: 'Rejected / flagged', type: 'scatter', symbol: 'diamond', symbolSize: 8, data: bad, itemStyle: { color: '#ffffff' } },
      { name: 'Corrected', type: 'scatter', symbol: 'triangle', symbolSize: 7, data: fixed, itemStyle: { color: '#7a7a7a' } }] }
}

export function psdOption(psd: { f: number[]; p: number[] }, bands: Record<string, [number, number]>): Option {
  const area = (k: string, c: string) => [{ name: k.toUpperCase(), xAxis: bands[k][0], itemStyle: { color: c, opacity: 0.14 }, label: { color: '#d4d4d4' } }, { xAxis: bands[k][1] }]
  return { ...base, ...tools, grid, tooltip: { trigger: 'axis', formatter: (p: any) => `${p[0].value[0].toFixed(3)} Hz<br/><b>${p[0].value[1].toFixed(1)}</b> ms²/Hz` },
    xAxis: { type: 'value', min: 0, max: 0.5, ...axis('Frequency (Hz)') }, yAxis: { type: 'value', ...axis('Power (ms²/Hz)', { nameGap: 46 }) },
    series: [{ type: 'line', data: psd.f.map((x, i) => [x, psd.p[i]]), showSymbol: false, lineStyle: { color: ORANGE, width: 1.8 }, areaStyle: { color: 'rgba(255,106,0,.12)' },
      markArea: { silent: true, data: [area('vlf', '#888') , area('lf', ORANGE), area('hf', '#ffffff')] as any } }] }
}

export function movementOption(t: number[], v: number[]): Option {
  return { ...base, ...tools, grid, dataZoom: zoom, tooltip: { trigger: 'axis', formatter: (p: any) => `${min(p[0].value[0])}<br/><b>${p[0].value[1].toFixed(2)}</b>` },
    xAxis: { type: 'value', ...axis('Time (mm:ss)'), axisLabel: { color: MUTED, formatter: min } }, yAxis: { type: 'value', ...axis('Acceleration RMS (source units)', { nameGap: 44 }) },
    series: [{ type: 'line', data: t.map((x, i) => [x, v[i]]), showSymbol: false, sampling: 'lttb', lineStyle: { color: '#c9c9c9', width: 1.3 }, areaStyle: { color: 'rgba(255,106,0,.10)' } }] }
}

export type PointX = 'poincare' | 'time_rr' | 'hr_rr' | 'time_drr'
export const POINT_MODES: { id: PointX; label: string; x: string; y: string }[] = [
  { id: 'poincare', label: 'RR(n) vs RR(n+1)', x: 'RR n (ms)', y: 'RR n+1 (ms)' },
  { id: 'hr_rr', label: 'HR vs RR', x: 'HR (bpm)', y: 'RR (ms)' },
  { id: 'time_rr', label: 'Time vs RR', x: 'Time (s)', y: 'RR (ms)' },
  { id: 'time_drr', label: 'Time vs successive difference', x: 'Time (s)', y: 'ΔRR (ms)' },
]
/** Configurable point-based physiological plot. NOT a proprietary "Point Care" definition: what is plotted is stated on the axes. */
export function pointOption(rr: RR, mode: PointX): Option {
  const t = rr.t_s || [], v = rr.rr_ms || [], h = rr.hr_bpm || [], a = rr.artifact || [], seg = rr.segment || []
  const ok: number[][] = [], out: number[][] = []
  const push = (flag: boolean, p: number[]) => (flag ? out : ok).push(p)
  for (let i = 0; i < t.length; i++) {
    const r = v[i]; if (r == null) continue
    if (mode === 'poincare') { if (i + 1 < t.length && seg[i + 1] === seg[i] && v[i + 1] != null) push(a[i] || a[i + 1], [r, v[i + 1] as number]) }
    else if (mode === 'hr_rr') push(a[i], [h[i], r])
    else if (mode === 'time_rr') push(a[i], [t[i], r])
    else if (i > 0 && seg[i] === seg[i - 1] && v[i - 1] != null) push(a[i] || a[i - 1], [t[i], r - (v[i - 1] as number)])
  }
  const m = POINT_MODES.find((x) => x.id === mode)!
  return { ...base, ...tools, grid, dataZoom: zoom.slice(0, 1), legend: { top: 0, left: 8, textStyle: { color: MUTED } },
    tooltip: { trigger: 'item', formatter: (p: any) => `${p.seriesName}<br/>${m.x}: ${p.value[0].toFixed(1)}<br/>${m.y}: ${p.value[1].toFixed(1)}` },
    xAxis: { type: 'value', ...axis(m.x), scale: true }, yAxis: { type: 'value', ...axis(m.y, { nameGap: 44 }), scale: true },
    series: [{ name: 'Accepted beats', type: 'scatter', symbolSize: 6, data: ok, itemStyle: { color: ORANGE, opacity: 0.75 } },
      { name: 'Outliers / artifacts', type: 'scatter', symbol: 'diamond', symbolSize: 9, data: out, itemStyle: { color: '#ffffff' } }] }
}

export function ecgOption(w: EcgWindow): Option {
  return { ...base, ...tools, backgroundColor: '#0B0B0B', grid: { left: 56, right: 20, top: 34, bottom: 62 }, dataZoom: zoom,
    tooltip: { trigger: 'axis', axisPointer: { type: 'line' }, formatter: (p: any) => `${p[0].value[0].toFixed(3)} s<br/>${p[0].value[1].toFixed(1)} (device units)` },
    legend: { top: 0, left: 8, textStyle: { color: MUTED } },
    xAxis: { type: 'value', ...axis('Time from ECG start (s)'), min: w.t.length ? w.t[0] : undefined, max: w.t.length ? w.t[w.t.length - 1] : undefined },
    yAxis: { type: 'value', ...axis('Filtered ECG (device units)', { nameGap: 44 }), scale: true },
    series: [{ name: 'ECG (filtered)', type: 'line', data: w.t.map((x, i) => [x, w.y[i]]), showSymbol: false, lineStyle: { color: BRIGHT, width: 1 } },
      { name: 'R-peaks', type: 'scatter', data: w.peaks_t.map((x, i) => [x, w.peaks_y[i]]), symbol: 'circle', symbolSize: 7, itemStyle: { color: '#ffffff', borderColor: ORANGE, borderWidth: 1.5 } }] }
}
