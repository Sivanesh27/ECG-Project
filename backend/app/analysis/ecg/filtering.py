"""ECG filtering. All parameters are configurable (see FilterConfig)."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy import signal


@dataclass
class FilterConfig:
    low_hz: float = 0.5          # also removes baseline wander (high-pass corner)
    high_hz: float = 40.0
    order: int = 3
    powerline_hz: float = 50.0   # 50 Hz default (India); 60 Hz configurable
    notch_q: float = 30.0
    notch_mode: str = "auto"     # auto | on | off
    notch_ratio_threshold: float = 3.0


def powerline_ratio(x: np.ndarray, fs: float, f0: float) -> float:
    """Power in +/-1 Hz around f0 relative to the neighbouring (f0-6..f0-3, f0+3..f0+6) background."""
    if f0 >= fs / 2 - 7 or len(x) < int(fs * 4):
        return 0.0
    f, p = signal.welch(x, fs=fs, nperseg=min(len(x), int(fs * 4)))
    band = (f >= f0 - 1) & (f <= f0 + 1)
    bg = ((f >= f0 - 6) & (f <= f0 - 3)) | ((f >= f0 + 3) & (f <= f0 + 6))
    if not band.any() or not bg.any() or p[bg].mean() <= 0:
        return 0.0
    return float(p[band].mean() / p[bg].mean())


def filter_ecg(x: np.ndarray, fs: float, cfg: FilterConfig | None = None) -> tuple[np.ndarray, dict]:
    cfg = cfg or FilterConfig()
    x = np.asarray(x, dtype=float)
    info = {"bandpass_hz": [cfg.low_hz, cfg.high_hz], "order": cfg.order, "notch_applied": False,
            "powerline_hz": cfg.powerline_hz}
    if len(x) < int(fs * 2):
        raise ValueError("Segment too short to filter.")
    x = x - np.nanmedian(x)
    nyq = fs / 2
    high = min(cfg.high_hz, nyq * 0.95)
    sos = signal.butter(cfg.order, [cfg.low_hz / nyq, high / nyq], btype="band", output="sos")
    y = signal.sosfiltfilt(sos, x)
    ratio = powerline_ratio(x, fs, cfg.powerline_hz)
    info["powerline_ratio"] = round(ratio, 2)
    do_notch = cfg.notch_mode == "on" or (cfg.notch_mode == "auto" and ratio > cfg.notch_ratio_threshold)
    if do_notch and cfg.powerline_hz < nyq * 0.98:
        b, a = signal.iirnotch(cfg.powerline_hz / nyq, cfg.notch_q)
        y = signal.filtfilt(b, a, y)
        info["notch_applied"] = True
    return y, info
