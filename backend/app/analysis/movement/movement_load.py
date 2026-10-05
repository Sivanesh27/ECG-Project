"""Movement metrics from acc_rms_avg.csv (3-s averaged accelerometer RMS in the sample data).
Verified against all sample summary.csv files:  movement_intensity == mean(acc_rms_avg)  and
movement_load == sum(acc_rms_avg * dt) / 3600  (dt = sampling step in seconds) to 3 decimals.
Documented as: intensity = mean RMS acceleration [source units]; load = time-integrated RMS [source units · hour]."""
from __future__ import annotations
import numpy as np


def movement_metrics(t_s, acc) -> dict:
    t = np.asarray(t_s, float); a = np.asarray(acc, float)
    ok = np.isfinite(a); t, a = t[ok], a[ok]
    if len(a) < 2:
        return {"intensity": None, "load": None, "peak": None, "dt_s": None}
    dt = float(np.median(np.diff(t)))
    return {"intensity": float(a.mean()), "load": float(np.sum(a * dt) / 3600.0), "peak": float(a.max()), "dt_s": dt,
            "algorithm": "intensity = mean(acc_rms); load = Σ acc_rms·Δt / 3600 (units: acc_rms-hours)"}
