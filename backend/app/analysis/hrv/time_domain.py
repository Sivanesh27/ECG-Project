"""Time-domain HRV. Input: NN intervals in ms organised as continuous segments.
Successive differences (RMSSD, SDSD, NN50, NN20) are only taken between ADJACENT accepted intervals
inside the same segment; they are never bridged across rejected beats or recording gaps."""
from __future__ import annotations
import numpy as np


def _succ_diffs(segments: list[np.ndarray]) -> np.ndarray:
    out = []
    for s in segments:
        s = np.asarray(s, float)
        if len(s) >= 2:
            ok = np.isfinite(s[:-1]) & np.isfinite(s[1:])
            out.append((s[1:] - s[:-1])[ok])
    return np.concatenate(out) if out else np.array([])


def time_domain(segments: list[np.ndarray], min_intervals: int = 30) -> dict:
    nn = np.concatenate([np.asarray(s, float)[np.isfinite(s)] for s in segments]) if segments else np.array([])
    n = len(nn)
    na = {"value": None, "reason": "N/A — insufficient valid data"}
    res: dict = {"n_nn": int(n)}
    if n < 2:
        for k in ("mean_rr", "median_rr", "min_rr", "max_rr", "mean_hr", "min_hr", "max_hr", "sdnn", "rmssd", "sdsd",
                  "nn50", "pnn50", "nn20", "pnn20", "cvnn", "hrv_triangular_index", "tinn"):
            res[k] = None
        return res
    hr = 60000.0 / nn
    res.update(mean_rr=float(nn.mean()), median_rr=float(np.median(nn)), min_rr=float(nn.min()), max_rr=float(nn.max()),
               mean_hr=float(hr.mean()), min_hr=float(hr.min()), max_hr=float(hr.max()))
    ok = n >= min_intervals
    d = _succ_diffs(segments)
    res["sdnn"] = float(np.std(nn, ddof=1)) if ok else None
    res["cvnn"] = float(np.std(nn, ddof=1) / nn.mean() * 100) if ok else None
    if len(d) >= max(2, min_intervals - 1):
        res["rmssd"] = float(np.sqrt(np.mean(d ** 2)))
        res["sdsd"] = float(np.std(d, ddof=1))
        res["nn50"] = int(np.sum(np.abs(d) > 50))
        res["nn20"] = int(np.sum(np.abs(d) > 20))
        res["pnn50"] = float(100.0 * res["nn50"] / len(d))
        res["pnn20"] = float(100.0 * res["nn20"] / len(d))
    else:
        for k in ("rmssd", "sdsd", "nn50", "nn20", "pnn50", "pnn20"):
            res[k] = None
    # HRV triangular index (bin 1/128 s) and TINN: only with enough data (>= 5 min worth, >= 200 NN)
    if n >= 200:
        bw = 1000.0 / 128.0
        edges = np.arange(nn.min(), nn.max() + 2 * bw, bw)
        h, e = np.histogram(nn, bins=edges)
        res["hrv_triangular_index"] = float(n / h.max())
        res["tinn"] = _tinn(h, e)
    else:
        res["hrv_triangular_index"] = None
        res["tinn"] = None
    return res


def _tinn(h: np.ndarray, e: np.ndarray) -> float | None:
    """Triangular interpolation (least-squares fit of a triangle to the histogram), Task Force 1996."""
    try:
        c = (e[:-1] + e[1:]) / 2
        m = int(np.argmax(h))
        best, bn, bm = np.inf, None, None
        for i in range(0, m):
            for j in range(m + 1, len(h)):
                tri = np.zeros(len(h))
                tri[i:m + 1] = np.linspace(0, h[m], m - i + 1)
                tri[m:j + 1] = np.linspace(h[m], 0, j - m + 1)
                err = float(np.sum((h - tri) ** 2))
                if err < best:
                    best, bn, bm = err, i, j
        return float(c[bm] - c[bn]) if bn is not None else None
    except Exception:  # noqa: BLE001
        return None
