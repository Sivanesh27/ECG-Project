from __future__ import annotations
import numpy as np

HRMAX_FORMULAS = {"220-age": lambda a: 220 - a, "208-0.7age": lambda a: 208 - 0.7 * a}
DEFAULT_ZONES = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]


def theoretical_hrmax(age: float, formula: str = "220-age", custom: float | None = None) -> float:
    if formula == "custom" and custom:
        return float(custom)
    return float(HRMAX_FORMULAS[formula](age))


def hr_reserve(hrmax: float, hr_rest: float | None):
    return None if hr_rest is None else float(hrmax - hr_rest)


def karvonen(hr_rest: float | None, hrmax: float, intensity: float):
    return None if hr_rest is None else float(hr_rest + intensity * (hrmax - hr_rest))


def zone_distribution(t_s: np.ndarray, hr: np.ndarray, hrmax: float, bounds=DEFAULT_ZONES, max_gap_s: float = 10.0) -> dict:
    """Time in zone from a (t, hr) series. Each sample holds for min(dt to next, max_gap_s) so that recording gaps do
    not count as zone time. Zone 0 = below the first boundary (reported separately)."""
    t = np.asarray(t_s, float); h = np.asarray(hr, float)
    ok = np.isfinite(h)
    t, h = t[ok], h[ok]
    if len(t) < 2:
        return {"zones": [], "total_s": 0.0}
    dt = np.minimum(np.diff(t, append=t[-1] + np.median(np.diff(t))), max_gap_s)
    edges = [bounds[0][0] * hrmax] + [b[1] * hrmax for b in bounds]
    idx = np.digitize(h, edges[:-1]) - 1 + 1          # 0 below first boundary; 1..n zones
    idx = np.where(h >= edges[-1], len(bounds), np.where(h < edges[0], 0, idx))
    total = float(dt.sum())
    zones = []
    for z in range(0, len(bounds) + 1):
        m = idx == z
        s = float(dt[m].sum())
        label = "Below Z1" if z == 0 else f"Zone {z}"
        lo = 0 if z == 0 else bounds[z - 1][0]
        hi = bounds[0][0] if z == 0 else bounds[z - 1][1]
        zones.append({"zone": z, "label": label, "lo_pct": lo * 100, "hi_pct": hi * 100,
                      "lo_bpm": lo * hrmax, "hi_bpm": hi * hrmax, "seconds": s,
                      "percent": (100 * s / total) if total else 0.0,
                      "avg_hr": float(np.average(h[m], weights=dt[m])) if m.any() and dt[m].sum() > 0 else None,
                      "peak_hr": float(h[m].max()) if m.any() else None})
    return {"zones": zones, "total_s": total}
