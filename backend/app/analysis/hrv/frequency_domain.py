"""Frequency-domain HRV (VLF/LF/HF) from irregularly sampled NN intervals.

Default method: Welch PSD on the NN tachogram resampled to an evenly spaced grid (cubic interpolation, 4 Hz) after
linear detrending ("welch"). Alternative: Lomb-Scargle periodogram computed directly on the uneven samples
("lomb"), which needs no resampling. Bands default to Task Force 1996 (VLF 0.0033-0.04, LF 0.04-0.15, HF 0.15-0.40 Hz)
and are configurable. Power is in ms^2 (integral of PSD in ms^2/Hz over the band).

Minimum-data gating (never reports a number that the recording cannot support):
  HF / LF / total need >= 120 s of valid data (and >= 30 NN); VLF needs >= 300 s.
  Only segments >= `min_segment_s` are analysed; PSDs of segments are averaged (weighted by duration).
LF/HF is a ratio of band powers. It must NOT be read as a direct measure of sympathovagal balance."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from scipy import interpolate, signal


@dataclass
class FreqConfig:
    vlf: tuple = (0.0033, 0.04)
    lf: tuple = (0.04, 0.15)
    hf: tuple = (0.15, 0.40)
    method: str = "welch"        # welch | lomb
    resample_hz: float = 4.0
    welch_window_s: float = 120.0
    welch_overlap: float = 0.5
    min_total_s: float = 120.0
    min_vlf_s: float = 300.0
    min_segment_s: float = 60.0


def _band_power(f, p, lo, hi) -> float:
    m = (f >= lo) & (f < hi)
    return float(np.trapezoid(p[m], f[m])) if m.sum() >= 2 else 0.0


def _segment_psd(t_s, rr, cfg: FreqConfig):
    t = np.asarray(t_s, float); x = np.asarray(rr, float)
    dur = t[-1] - t[0]
    if cfg.method == "lomb":
        fgrid = np.linspace(0.0033, 0.5, 600)
        xc = x - x.mean()
        pg = signal.lombscargle(t, xc, 2 * np.pi * fgrid, normalize=False)
        psd = pg
        # scale so that integral over [0, fs/2] equals variance (Parseval) -> ms^2/Hz
        psd = psd * (np.var(xc) / max(np.trapezoid(psd, fgrid), 1e-12))
        return fgrid, psd, dur
    fs = cfg.resample_hz
    grid = np.arange(t[0], t[-1], 1 / fs)
    y = interpolate.interp1d(t, x, kind="cubic", bounds_error=False, fill_value=(x[0], x[-1]))(grid)
    y = signal.detrend(y, type="linear")
    nper = int(min(len(y), cfg.welch_window_s * fs))
    f, p = signal.welch(y, fs=fs, window="hann", nperseg=nper, noverlap=int(nper * cfg.welch_overlap), detrend=False)
    return f, p, dur


def frequency_domain(segments_t: list[np.ndarray], segments_rr: list[np.ndarray], cfg: FreqConfig | None = None) -> dict:
    cfg = cfg or FreqConfig()
    out = {"method": cfg.method, "bands": {"vlf": cfg.vlf, "lf": cfg.lf, "hf": cfg.hf}, "vlf": None, "lf": None, "hf": None,
           "lf_hf": None, "total_power": None, "lf_nu": None, "hf_nu": None, "peak_lf_hz": None, "peak_hf_hz": None,
           "psd": None, "analysed_s": 0.0, "n_segments": 0, "notes": []}
    psds, weights, total = [], [], 0.0
    for t, rr in zip(segments_t, segments_rr):
        t = np.asarray(t, float); rr = np.asarray(rr, float)
        ok = np.isfinite(rr)
        t, rr = t[ok], rr[ok]
        if len(rr) < 10 or (t[-1] - t[0]) < cfg.min_segment_s:
            continue
        f, p, dur = _segment_psd(t, rr, cfg)
        psds.append((f, p)); weights.append(dur); total += dur
    out["analysed_s"] = round(total, 1)
    out["n_segments"] = len(psds)
    if not psds or total < cfg.min_total_s:
        out["notes"].append("N/A — insufficient valid data: need >= %d s of artifact-free RR data for spectral HRV." % cfg.min_total_s)
        return out
    f0 = psds[0][0]
    P = np.zeros_like(f0)
    for (f, p), w in zip(psds, weights):
        P += np.interp(f0, f, p) * w
    P /= np.sum(weights)
    lf = _band_power(f0, P, *cfg.lf); hf = _band_power(f0, P, *cfg.hf)
    out["lf"], out["hf"] = lf, hf
    out["lf_hf"] = float(lf / hf) if hf > 0 else None
    if lf + hf > 0:
        out["lf_nu"], out["hf_nu"] = float(100 * lf / (lf + hf)), float(100 * hf / (lf + hf))
    if total >= cfg.min_vlf_s:
        vlf = _band_power(f0, P, *cfg.vlf)
        out["vlf"] = vlf
        out["total_power"] = vlf + lf + hf
    else:
        out["notes"].append("VLF not reported: recording shorter than %d s (VLF requires long recordings). Total power not reported." % cfg.min_vlf_s)
    for key, b in (("peak_lf_hz", cfg.lf), ("peak_hf_hz", cfg.hf)):
        m = (f0 >= b[0]) & (f0 < b[1])
        if m.any():
            out[key] = float(f0[m][np.argmax(P[m])])
    keep = f0 <= 0.5
    step = max(1, keep.sum() // 400)
    out["psd"] = {"f": f0[keep][::step].round(5).tolist(), "p": P[keep][::step].tolist()}
    return out
