"""Poincare descriptors (SD1, SD2) computed on adjacent accepted NN pairs within segments."""
from __future__ import annotations
import numpy as np


def poincare(segments: list[np.ndarray], min_pairs: int = 30) -> dict:
    x, y = [], []
    for s in segments:
        s = np.asarray(s, float)
        if len(s) >= 2:
            a, b = s[:-1], s[1:]
            ok = np.isfinite(a) & np.isfinite(b)
            x.append(a[ok]); y.append(b[ok])
    if not x:
        return {"sd1": None, "sd2": None, "sd1_sd2": None, "points": None}
    x, y = np.concatenate(x), np.concatenate(y)
    if len(x) < min_pairs:
        return {"sd1": None, "sd2": None, "sd1_sd2": None, "points": None}
    d = (y - x) / np.sqrt(2); s_ = (y + x) / np.sqrt(2)
    sd1, sd2 = float(np.std(d, ddof=1)), float(np.std(s_, ddof=1))
    return {"sd1": sd1, "sd2": sd2, "sd1_sd2": sd1 / sd2 if sd2 else None,
            "points": np.stack([x, y], 1)[:2000].round(1).tolist()}
