"""R-peak detection: Pan-Tompkins-style detector implemented with NumPy/SciPy (no external ECG library).

Steps: 5-15 Hz band-pass -> derivative -> squaring -> moving-window integration (~150 ms) -> adaptive
local thresholding -> refinement to the local extremum of the filtered ECG (+/-75 ms, polarity-aware)
-> refractory period (200 ms) -> search-back for missed beats when RR > 1.66 x local median.
Reference: Pan J, Tompkins WJ. IEEE Trans Biomed Eng 1985;32(3):230-236.
"""
from __future__ import annotations
import numpy as np
from scipy import signal


def _polarity(y: np.ndarray) -> int:
    hi, lo = np.percentile(y, 99.5), np.percentile(y, 0.5)
    return 1 if abs(hi) >= abs(lo) else -1


def detect_r_peaks(y: np.ndarray, fs: float, refractory_s: float = 0.2, search_back: bool = True) -> np.ndarray:
    """Return sample indices of R peaks in the (already filtered) ECG y."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < fs * 3:
        return np.array([], dtype=int)
    nyq = fs / 2
    sos = signal.butter(2, [5 / nyq, min(15, nyq * 0.9) / nyq], btype="band", output="sos")
    z = signal.sosfiltfilt(sos, y)
    d = np.gradient(z)
    sq = d ** 2
    w = max(1, int(0.150 * fs))
    mwi = np.convolve(sq, np.ones(w) / w, mode="same")
    dist = max(1, int(refractory_s * fs))
    cand, _ = signal.find_peaks(mwi, distance=dist)
    if len(cand) == 0:
        return np.array([], dtype=int)
    amp = mwi[cand]
    # adaptive threshold: fraction of the local (+/-6 s) robust high level
    half = int(6 * fs)
    keep = []
    for i, c in enumerate(cand):
        loc = amp[(cand > c - half) & (cand < c + half)]
        level = np.percentile(loc, 75) if len(loc) >= 4 else np.max(loc)
        if amp[i] >= 0.30 * level:
            keep.append(i)
    cand = cand[keep]
    peaks = _refine(y, cand, fs)
    if search_back and len(peaks) > 3:
        peaks = _search_back(y, mwi, peaks, fs, dist)
    peaks = _dedupe(y, peaks, dist)
    return _prune(y, peaks, fs)


def _prune(y: np.ndarray, peaks: np.ndarray, fs: float) -> np.ndarray:
    """Remove likely T-waves / noise: (1) Pan-Tompkins slope rule for peaks <360 ms after the previous beat,
    (2) amplitude consistency: drop peaks far smaller than the local median R amplitude."""
    if len(peaks) < 5:
        return peaks
    pol = _polarity(y)
    d = np.abs(np.gradient(y))
    w = max(1, int(0.075 * fs))
    slope = np.array([d[max(0, p - w):p + w + 1].max() for p in peaks])
    amp = np.abs(y[peaks] * pol)
    keep = np.ones(len(peaks), bool)
    last = 0
    for i in range(1, len(peaks)):
        if (peaks[i] - peaks[last]) / fs < 0.36 and slope[i] < 0.5 * slope[last]:
            keep[i] = False
        else:
            last = i
    pk, am = peaks[keep], amp[keep]
    half = int(10 * fs)
    ok = np.ones(len(pk), bool)
    for i, p in enumerate(pk):
        loc = am[(pk > p - half) & (pk < p + half)]
        if len(loc) >= 5 and am[i] < 0.35 * np.median(loc):
            ok[i] = False
    return pk[ok]


def _refine(y: np.ndarray, cand: np.ndarray, fs: float) -> np.ndarray:
    pol = _polarity(y)
    r = max(1, int(0.075 * fs))
    out = []
    for c in cand:
        a, b = max(0, c - r - int(0.05 * fs)), min(len(y), c + r)
        seg = y[a:b] * pol
        out.append(a + int(np.argmax(seg)))
    return np.unique(np.array(out, dtype=int))


def _search_back(y, mwi, peaks, fs, dist):
    rr = np.diff(peaks)
    med = np.median(rr)
    added = []
    for i, r in enumerate(rr):
        if r > 1.66 * med:
            a, b = peaks[i] + dist, peaks[i + 1] - dist
            if b > a:
                j = a + int(np.argmax(mwi[a:b]))
                ref = np.percentile(mwi[peaks], 25)
                if mwi[j] > 0.5 * ref:
                    added.append(_refine(y, np.array([j]), fs)[0])
    return np.unique(np.concatenate([peaks, np.array(added, dtype=int)])) if added else peaks


def _dedupe(y, peaks, dist):
    if len(peaks) < 2:
        return peaks
    pol = _polarity(y)
    out = [peaks[0]]
    for p in peaks[1:]:
        if p - out[-1] < dist:
            if y[p] * pol > y[out[-1]] * pol:
                out[-1] = p
        else:
            out.append(p)
    return np.array(out, dtype=int)
