"""Banister TRIMP (exponential, HR-reserve weighted).
TRIMP = sum_i  dt_i[min] * HRr_i * 0.64 * exp(b * HRr_i),   HRr = (HR - HRrest)/(HRmax - HRrest) clipped to [0, 1]
b = 1.92 (male) / 1.67 (female) / 1.80 (unspecified; midpoint, configurable).
This is a published, documented method; it is NOT the proprietary 'training load' of the source device, and values are
not expected to be on the same scale."""
from __future__ import annotations
import numpy as np

B = {"male": 1.92, "female": 1.67}


def banister_trimp(t_s, hr, hr_rest: float, hrmax: float, sex: str | None = None, b: float | None = None,
                   max_gap_s: float = 10.0) -> dict:
    t = np.asarray(t_s, float); h = np.asarray(hr, float)
    ok = np.isfinite(h); t, h = t[ok], h[ok]
    if len(t) < 2 or hrmax <= hr_rest:
        return {"trimp": None, "duration_min": None, "intensity": None, "b": None}
    b = b if b is not None else B.get((sex or "").lower(), 1.80)
    dt_min = np.minimum(np.diff(t, append=t[-1] + np.median(np.diff(t))), max_gap_s) / 60.0
    hrr = np.clip((h - hr_rest) / (hrmax - hr_rest), 0, 1)
    trimp = float(np.sum(dt_min * hrr * 0.64 * np.exp(b * hrr)))
    dur = float(dt_min.sum())
    return {"trimp": trimp, "duration_min": dur, "intensity": trimp / dur if dur else None, "b": b,
            "formula": "Banister TRIMP: Σ Δt[min]·HRr·0.64·e^(b·HRr)"}
