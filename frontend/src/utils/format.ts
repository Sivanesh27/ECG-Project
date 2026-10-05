export const NA = 'N/A'

export function fmt(v: number | null | undefined, nd = 1): string {
  return v === null || v === undefined || Number.isNaN(v) ? NA : v.toLocaleString(undefined, { minimumFractionDigits: nd, maximumFractionDigits: nd })
}
export function fmtDuration(sec?: number | null): string {
  if (sec === null || sec === undefined) return NA
  const s = Math.round(sec); const h = Math.floor(s / 3600); const m = Math.floor((s % 3600) / 60); const r = s % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}` : `${m}:${String(r).padStart(2, '0')}`
}
export function fmtDate(iso?: string | null): string {
  if (!iso) return NA
  const d = new Date(iso)
  return isNaN(d.getTime()) ? NA : d.toLocaleString(undefined, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
export function bmi(h?: number, w?: number): { value: number; category: string } | null {
  if (!h || !w) return null
  const v = w / ((h / 100) ** 2)
  return { value: Math.round(v * 10) / 10, category: v < 18.5 ? 'Underweight range' : v < 25 ? 'Normal range' : v < 30 ? 'Overweight range' : 'Obesity range' }
}
export function median(a: number[]): number | null {
  if (!a.length) return null
  const s = [...a].sort((x, y) => x - y); const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}
export function passwordProblems(p: string): string[] {
  const out: string[] = []
  if (p.length < 10) out.push('at least 10 characters')
  if (!/[a-z]/.test(p)) out.push('a lowercase letter')
  if (!/[A-Z]/.test(p)) out.push('an uppercase letter')
  if (!/\d/.test(p)) out.push('a digit')
  return out
}
