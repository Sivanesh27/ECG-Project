"""Server-side downsampling for the browser. Analysis always uses full-resolution data."""
from __future__ import annotations
import numpy as np


def minmax_decimate(t: np.ndarray, y: np.ndarray, max_points: int) -> tuple[np.ndarray, np.ndarray]:
    """Per-bucket min & max (preserves QRS peaks) -> <= max_points samples."""
    n = len(t)
    if n <= max_points:
        return t, y
    buckets = max(1, max_points // 2)
    edges = np.linspace(0, n, buckets + 1).astype(int)
    ti, yi = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        if b <= a:
            continue
        seg = y[a:b]
        i0, i1 = a + int(np.argmin(seg)), a + int(np.argmax(seg))
        for i in sorted({i0, i1}):
            ti.append(t[i]); yi.append(y[i])
    return np.array(ti), np.array(yi)


def ecg_window(arrays: dict, t0: float | None, t1: float | None, max_points: int = 8000) -> dict:
    t, y, seg, pk = arrays["ecg_t"], arrays["ecg_y"], arrays["ecg_seg"], arrays["peak_idx"]
    lo = t[0] if t0 is None else t0
    hi = t[-1] if t1 is None else t1
    i0, i1 = int(np.searchsorted(t, lo)), int(np.searchsorted(t, hi, side="right"))
    tw, yw = t[i0:i1], y[i0:i1]
    td, yd = minmax_decimate(tw, yw, max_points)
    pk = pk[(pk >= i0) & (pk < i1)]
    return {"t": np.round(td, 4).tolist(), "y": np.round(yd.astype(float), 2).tolist(),
            "peaks_t": np.round(t[pk], 4).tolist(), "peaks_y": np.round(y[pk].astype(float), 2).tolist(),
            "t_min": float(t[0]), "t_max": float(t[-1]), "n_total": int(len(t)), "n_window": int(i1 - i0),
            "downsampled": bool(len(tw) > max_points),
            "segments": _segment_bounds(t, seg)}


def _segment_bounds(t, seg):
    out = []
    for s in np.unique(seg):
        m = np.flatnonzero(seg == s)
        out.append({"segment": int(s), "start": float(t[m[0]]), "end": float(t[m[-1]])})
    return out
