import { Link } from 'react-router-dom'
import { Logo } from '../layouts/AppLayout'

// Decorative brand artwork only (a stylised trace) -- it is NOT physiological data.
const TRACE = 'M0 120 H140 l12 -10 l12 10 H230 l10 14 l12 -112 l14 150 l10 -52 H330 q26 -38 52 0 H470 H610 l12 -10 l12 10 H700 l10 14 l12 -112 l14 150 l10 -52 H800 q26 -38 52 0 H940 H1100 l12 -10 l12 10 H1190 l10 14 l12 -112 l14 150 l10 -52 H1290'

const FEATURES = [
  ['ECG analysis', 'Chunked device exports are stitched in time order, filtered, and scanned for R-peaks. Gaps are detected, never bridged.'],
  ['HRV analytics', 'SDNN, RMSSD, pNN50 and LF/HF/VLF from artifact-screened NN intervals, withheld when the data cannot support them.'],
  ['Training load', 'Heart-rate zones from an estimated HRmax and a documented Banister TRIMP, shown beside the device’s own value.'],
  ['Movement analysis', 'Accelerometer RMS over time with load and intensity, or a plain “not available” when there is none.'],
  ['Scientific reports', 'Every number carries its method, unit and limits. Export PDF, CSV and JSON.'],
  ['Secure user data', 'Each recording belongs to one account. Files are never reachable by URL, and you can delete everything at any time.'],
]

export default function Landing() {
  return (
    <div className="min-h-full bg-ink">
      <header className="max-w-6xl mx-auto px-5 h-16 flex items-center justify-between"><Logo />
        <nav className="flex gap-3"><Link to="/login" className="btn-ghost">Sign in</Link><Link to="/register" className="btn-primary">Start analysis</Link></nav></header>
      <section className="relative overflow-hidden border-b border-line">
        <svg className="absolute inset-x-0 top-1/2 -translate-y-1/2 w-full opacity-60" viewBox="0 0 1290 240" preserveAspectRatio="none" aria-hidden>
          <path className="trace-draw" d={TRACE} fill="none" stroke="#FF6A00" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
        </svg>
        <div className="relative max-w-6xl mx-auto px-5 py-28 md:py-40">
          <h1 className="text-5xl md:text-7xl font-bold leading-[1.02] max-w-3xl">Advanced ECG &amp; HRV Analytics</h1>
          <p className="mt-6 text-lg text-neutral-300 max-w-xl">Transform raw physiological recordings into scientifically structured heart-rate, HRV, training-load and movement insights.</p>
          <div className="mt-9 flex gap-3"><Link to="/register" className="btn-primary text-base px-6 py-3">Start analysis</Link><Link to="/login" className="btn-ghost text-base px-6 py-3">Sign in</Link></div>
        </div>
      </section>
      <section className="max-w-6xl mx-auto px-5 py-16 grid gap-px bg-line border border-line md:grid-cols-3">
        {FEATURES.map(([t, d]) => <div key={t} className="bg-ink p-6"><h2 className="font-semibold text-lg text-orange">{t}</h2><p className="mt-2 text-sm text-neutral-300 leading-relaxed">{d}</p></div>)}
      </section>
      <footer className="border-t border-line px-5 py-6 text-center text-xs text-muted">A research and analysis tool, not a medical device. It does not diagnose arrhythmia, cardiac or autonomic conditions.</footer>
    </div>
  )
}
