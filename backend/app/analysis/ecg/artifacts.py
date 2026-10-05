"""RR artifact detection and correction.

Rules (all thresholds configurable):
  range  : RR < min_rr_ms or RR > max_rr_ms                        (physiological range)
  long   : RR ~ 2x the local median (suspected missed beat)
  short  : RR < short_ratio x local median (suspected extra beat / ectopic / noise)
  jump   : |RR - local median| > jump_ratio x local median          (sudden change)
Local median = centred running median over `window` beats (robust to the HR trends of exercise).
This is an interval-based screening method, not an ectopic-beat classifier; no diagnosis is made.

Correction modes: reject (exclude), interpolate (linear in time between neighbouring accepted beats), keep (raw).
Default: interpolate for the tachogram / spectral analysis; time-domain metrics always use accepted NN only, and
successive differences are computed only between adjacent accepted intervals.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.ndimage import median_filter


@dataclass
class ArtifactConfig:
    min_rr_ms: float = 300.0
    max_rr_ms: float = 2000.0
    window: int = 11
    jump_ratio: float = 0.30
    short_ratio: float = 0.65
    long_ratio: float = 1.65
    mode: str = "interpolate"   # reject | interpolate | keep


def detect_artifacts(rr_ms: np.ndarray, cfg: ArtifactConfig | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Return (flag bool array, reason string array). rr in ms, one segment (no gaps inside)."""
    cfg = cfg or ArtifactConfig()
    rr = np.asarray(rr_ms, dtype=float)
    n = len(rr)
    reason = np.array([""] * n, dtype=object)
    if n == 0:
        return np.zeros(0, bool), reason
    w = min(cfg.window, n if n % 2 else n - 1) or 1
    med = median_filter(rr, size=w, mode="nearest")
    rng = (rr < cfg.min_rr_ms) | (rr > cfg.max_rr_ms) | ~np.isfinite(rr)
    long_ = (rr > cfg.long_ratio * med) & ~rng
    short = (rr < cfg.short_ratio * med) & ~rng
    jump = (np.abs(rr - med) > cfg.jump_ratio * med) & ~rng & ~long_ & ~short
    reason[jump] = "jump"
    reason[short] = "short"
    reason[long_] = "long"
    reason[rng] = "range"
    return reason != "", reason


def correct_rr(t_s: np.ndarray, rr_ms: np.ndarray, flag: np.ndarray, mode: str = "interpolate") -> np.ndarray:
    """Corrected RR series (NaN where rejected)."""
    rr = np.asarray(rr_ms, dtype=float).copy()
    if mode == "keep" or not flag.any():
        return rr
    if mode == "reject":
        rr[flag] = np.nan
        return rr
    good = ~flag
    if good.sum() < 2:
        rr[flag] = np.nan
        return rr
    rr[flag] = np.interp(t_s[flag], t_s[good], rr[good])
    return rr
