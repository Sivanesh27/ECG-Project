"""RR extraction from R-peaks, per continuous segment."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .artifacts import ArtifactConfig, detect_artifacts, correct_rr


def build_rr_table(peak_times_s: np.ndarray, segment_ids: np.ndarray, cfg: ArtifactConfig | None = None) -> pd.DataFrame:
    """peak_times_s: R-peak times (s from recording start); segment_ids: segment of each peak.
    RR_i = t(R_{i+1}) - t(R_i) (ms); never computed across a discontinuity.
    Columns: t_s (time of the ending beat), rr_ms, hr_bpm, segment, artifact, reason, rr_corrected_ms, status
    """
    cfg = cfg or ArtifactConfig()
    rows = []
    for seg in np.unique(segment_ids):
        t = peak_times_s[segment_ids == seg]
        if len(t) < 2:
            continue
        rr = np.diff(t) * 1000.0
        tt = t[1:]
        flag, reason = detect_artifacts(rr, cfg)
        corr = correct_rr(tt, rr, flag, cfg.mode)
        df = pd.DataFrame({"t_s": tt, "rr_ms": rr, "hr_bpm": 60000.0 / rr, "segment": int(seg),
                           "artifact": flag, "reason": reason, "rr_corrected_ms": corr})
        # dup beats (< 1 ms apart) are flagged by the range rule already
        df["status"] = np.where(~flag, "normal",
                                np.where(cfg.mode == "reject", "rejected",
                                         np.where(cfg.mode == "interpolate", "corrected", "artifact")))
        rows.append(df)
    if not rows:
        return pd.DataFrame(columns=["t_s", "rr_ms", "hr_bpm", "segment", "artifact", "reason", "rr_corrected_ms", "status"])
    return pd.concat(rows, ignore_index=True)
