"""End-to-end analysis of one ParsedSession -> JSON-serialisable results + arrays for storage."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional
import numpy as np
import pandas as pd

from .ingestion.parser import ParsedSession
from .ecg.filtering import FilterConfig, filter_ecg
from .ecg.peaks import detect_r_peaks
from .ecg.artifacts import ArtifactConfig
from .ecg.rr import build_rr_table
from .hrv.time_domain import time_domain
from .hrv.frequency_domain import FreqConfig, frequency_domain
from .hrv.nonlinear import poincare
from .hrv.metadata import METRICS
from .training.hr_zones import DEFAULT_ZONES, karvonen, theoretical_hrmax, hr_reserve, zone_distribution
from .training.trimp import banister_trimp
from .movement.movement_load import movement_metrics

STEPS = ["Uploading", "Validating", "Parsing", "Detecting ECG", "Filtering", "Detecting R-peaks",
         "Generating RR intervals", "Removing artifacts", "Calculating HRV", "Calculating HR zones",
         "Calculating training load", "Calculating movement load", "Generating visualizations", "Complete"]


@dataclass
class Settings:
    hrmax_formula: str = "220-age"          # 220-age | 208-0.7age | custom
    hrmax_custom: Optional[float] = None
    zones: list = field(default_factory=lambda: [list(z) for z in DEFAULT_ZONES])
    filter: dict = field(default_factory=dict)
    artifact: dict = field(default_factory=dict)
    freq: dict = field(default_factory=dict)
    sampling_rate_override: Optional[float] = None
    max_artifact_pct_for_hrv: float = 25.0
    min_nn_for_hrv: int = 30


def _f(x):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else (float(x) if isinstance(x, (np.floating, float)) else x)


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    return o


def duration_class(sec: float) -> str:
    return ("<1 min" if sec < 60 else "1-5 min" if sec < 300 else "5-10 min" if sec < 600
            else "10-30 min" if sec < 1800 else ">30 min")


def quality_status(artifact_pct: float | None) -> str:
    if artifact_pct is None:
        return "UNKNOWN"
    return "GOOD" if artifact_pct < 5 else "ACCEPTABLE" if artifact_pct < 15 else "POOR"


def analyse_session(s: ParsedSession, subject: dict, settings: Settings | None = None,
                    progress: Callable[[str], None] | None = None):
    st = settings or Settings()
    prog = progress or (lambda _s: None)
    warnings: list[dict] = [{"code": "PARSER", "level": "info", "message": w} for w in s.warnings]
    arrays: dict = {}
    t0 = s.start_time
    res: dict = {"parameters": asdict(st)}

    # ---------------------------------------------------------------- recording info
    ecg_valid_s = 0.0
    if s.ecg is not None:
        ecg_valid_s = float(len(s.ecg) / s.ecg_fs)
    if st.sampling_rate_override and s.ecg is None and s.quality.get("unknown_fs_samples"):
        warnings.append({"code": "UNKNOWN_FS", "level": "warn", "message":
                         "Sampling rate override cannot be applied: this session has no usable chunk timing."})
    sess_dur = None
    if s.summary and any(s.summary.get(f"zone_{i}_duration") is not None for i in range(6)):
        sess_dur = sum(float(s.summary.get(f"zone_{i}_duration") or 0) for i in range(6)) / 1000.0
    if s.hr is not None and len(s.hr) > 1:
        sess_dur = max(sess_dur or 0, (s.hr.t_abs.iloc[-1] - s.hr.t_abs.iloc[0]).total_seconds())
    elif s.corrected_hr is not None and len(s.corrected_hr) > 1:
        sess_dur = max(sess_dur or 0, (s.corrected_hr.t_abs.iloc[-1] - s.corrected_hr.t_abs.iloc[0]).total_seconds())
    res["recording"] = {"start_time": t0, "end_time": s.end_time, "ecg_start_time": s.ecg_start, "session_duration_s": sess_dur,
                        "ecg_valid_duration_s": ecg_valid_s, "ecg_fs_hz": s.ecg_fs, "fs_source": s.fs_source,
                        "ecg_samples": int(len(s.ecg)) if s.ecg is not None else 0,
                        "ecg_duration_class": duration_class(ecg_valid_s) if ecg_valid_s else None,
                        "availability": s.availability()}
    av = s.availability()
    if not av["ecg"]:
        warnings.append({"code": "MISSING_ECG", "level": "warn", "message": "No usable ECG for this session — HRV from ECG is not available."})
    if not av["hr"]:
        warnings.append({"code": "MISSING_HR", "level": "warn", "message": "MISSING HR DATA"})
    if not av["movement"]:
        warnings.append({"code": "MISSING_MOVEMENT", "level": "info", "message": "Movement data not available for this session."})

    # ---------------------------------------------------------------- ECG -> peaks -> RR
    rr_tab = pd.DataFrame()
    q = {"samples": int(s.quality.get("samples", 0)), "missing_samples": int(s.quality.get("missing_samples", 0)),
         "duplicate_samples": int(s.quality.get("duplicate_samples", 0)), "gaps": s.quality.get("gaps", []),
         "n_segments": int(s.quality.get("n_segments", 0))}
    acfg = ArtifactConfig(**st.artifact)
    fcfg = FilterConfig(**st.filter)
    if s.ecg is not None and len(s.ecg) > 0:
        prog("Filtering")
        fs = float(s.ecg_fs)
        t_all, y_all, seg_all, pk_idx_all = [], [], [], []
        fil_info = None
        offset = 0
        peak_t, peak_seg = [], []
        for seg, g in s.ecg.groupby("segment"):
            if len(g) < fs * 4:
                warnings.append({"code": "SHORT_SEGMENT", "level": "info", "message": f"ECG segment {int(seg)} is shorter than 4 s and was skipped."})
                continue
            y, fil_info = filter_ecg(g.v.values, fs, fcfg)
            prog("Detecting R-peaks")
            p = detect_r_peaks(y, fs)
            tt = g.t.values
            t_all.append(tt); y_all.append(y); seg_all.append(g.segment.values)
            pk_idx_all.append(p + offset)
            peak_t.append(tt[p]); peak_seg.append(np.full(len(p), seg))
            offset += len(g)
        if t_all:
            arrays["ecg_t"] = np.concatenate(t_all).astype(np.float64)
            arrays["ecg_y"] = np.concatenate(y_all).astype(np.float32)
            arrays["ecg_seg"] = np.concatenate(seg_all).astype(np.int16)
            arrays["peak_idx"] = np.concatenate(pk_idx_all).astype(np.int64)
            pt, ps = np.concatenate(peak_t), np.concatenate(peak_seg)
            prog("Generating RR intervals")
            rr_tab = build_rr_table(pt, ps, acfg)
            prog("Removing artifacts")
            res["ecg_processing"] = {"filter": fil_info, "detector": "Pan-Tompkins-style (NumPy/SciPy), see peaks.py",
                                     "n_peaks": int(len(pt))}
            # device reference check (is_pulse flags): informational only
            dev = int(s.ecg.pulse.sum()) if "pulse" in s.ecg else 0
            res["ecg_processing"]["device_pulse_flags"] = dev
    elif s.rr_ms is not None and len(s.rr_ms):
        t = s.rr_ms.t_s.values
        pt = np.concatenate([[t[0] - s.rr_ms.rr_ms.values[0] / 1000.0], t])
        rr_tab = build_rr_table(pt, np.zeros(len(pt), int), acfg)
        res["ecg_processing"] = {"note": "RR-only upload; no ECG processing."}

    n_rr = len(rr_tab)
    n_art = int(rr_tab.artifact.sum()) if n_rr else 0
    art_pct = (100.0 * n_art / n_rr) if n_rr else None
    q.update({"n_peaks": int(n_rr + (rr_tab.segment.nunique() if n_rr else 0)), "n_rr": n_rr, "accepted_beats": n_rr - n_art,
              "rejected_beats": n_art if acfg.mode == "reject" else 0,
              "interpolated_beats": n_art if acfg.mode == "interpolate" else 0, "flagged_beats": n_art,
              "artifact_pct": art_pct, "signal_quality_pct": (100 - art_pct) if art_pct is not None else None,
              "valid_pct": (100 * (n_rr - n_art) / n_rr) if n_rr else None, "status": quality_status(art_pct),
              "device_hr_quality_mean": _f(s.hr_quality.value.mean()) if s.hr_quality is not None and len(s.hr_quality) else None})
    if art_pct is not None and art_pct >= 15:
        warnings.append({"code": "HIGH_ARTIFACT_RATE", "level": "warn", "message": f"HIGH ARTIFACT RATE ({art_pct:.1f}%)"})
    if n_rr and n_rr < st.min_nn_for_hrv:
        warnings.append({"code": "INSUFFICIENT_RR", "level": "warn", "message": "INSUFFICIENT RR INTERVALS for reliable HRV."})
    if ecg_valid_s and ecg_valid_s < 300:
        warnings.append({"code": "SHORT_RECORDING", "level": "info", "message":
                         f"INSUFFICIENT RECORDING DURATION for long-term HRV: {ecg_valid_s:.0f} s of valid ECG. Results are ultra-short-term (<5 min) and VLF/Total power are not reported."})
    if q["gaps"]:
        warnings.append({"code": "IRREGULAR_SAMPLING", "level": "info", "message": f"{len(q['gaps'])} ECG discontinuities detected; RR intervals are never computed across a gap."})
    res["quality"] = q

    # ---------------------------------------------------------------- HRV
    prog("Calculating HRV")
    hrv_ok = n_rr >= st.min_nn_for_hrv and (art_pct is None or art_pct <= st.max_artifact_pct_for_hrv)
    if n_rr and not hrv_ok and n_rr >= st.min_nn_for_hrv:
        warnings.append({"code": "LOW_ECG_QUALITY", "level": "error", "message": "LOW ECG QUALITY: signal quality is insufficient for reliable HRV; metrics withheld (N/A)."})
    if n_rr:
        segs_nn, segs_t = [], []
        for seg, g in rr_tab.groupby("segment"):
            col = g.rr_corrected_ms.values if acfg.mode != "reject" else np.where(g.artifact.values, np.nan, g.rr_ms.values)
            if acfg.mode == "keep":
                col = g.rr_ms.values
            segs_nn.append(col); segs_t.append(g.t_s.values)
        if hrv_ok:
            res["hrv_time"] = time_domain(segs_nn, st.min_nn_for_hrv)
            fq = FreqConfig(**{**{k: tuple(v) if isinstance(v, list) else v for k, v in st.freq.items()}})
            # spectral analysis needs evenly-usable tachogram: for 'reject' mode, drop NaNs (spectrum is then approximate)
            res["hrv_freq"] = frequency_domain(segs_t, segs_nn, fq)
            res["hrv_nonlinear"] = poincare(segs_nn, st.min_nn_for_hrv)
        else:
            res["hrv_time"] = {"n_nn": 0, "withheld": True}
            res["hrv_freq"] = {"withheld": True, "notes": ["N/A — insufficient valid data"]}
            res["hrv_nonlinear"] = {}
    else:
        res["hrv_time"], res["hrv_freq"], res["hrv_nonlinear"] = {"n_nn": 0}, {"notes": ["N/A — insufficient valid data"]}, {}
    res["metric_metadata"] = METRICS

    # ---------------------------------------------------------------- HR (primary series)
    hr_t = hr_v = None
    src = None
    for name, d in (("corrected_hr_avg.csv", s.corrected_hr), ("hr.csv", s.hr)):
        if d is not None and d.value.notna().sum() > 1:
            dd = d.dropna(subset=["value"])
            hr_t = (dd.t_abs - t0).dt.total_seconds().values
            hr_v = dd.value.values.astype(float)
            src = name
            break
    if hr_t is None and n_rr:
        hr_t, hr_v, src = rr_tab.t_s.values, rr_tab.hr_bpm.values, "ECG-derived (RR)"
    hr_res: dict = {"series_source": src}
    age = _f(subject.get("age"))
    hrmax = None
    if age is not None:
        hrmax = theoretical_hrmax(age, st.hrmax_formula, st.hrmax_custom)
    elif st.hrmax_formula == "custom" and st.hrmax_custom:
        hrmax = float(st.hrmax_custom)
    if subject.get("max_hr"):
        hr_res["measured_hrmax_provided"] = float(subject["max_hr"])
    if hr_v is not None and len(hr_v):
        hr_res.update(avg=float(np.mean(hr_v)), max=float(np.max(hr_v)), min=float(np.min(hr_v)),
                      median=float(np.median(hr_v)), n=int(len(hr_v)))
        arrays["hr_t"], arrays["hr_v"] = np.asarray(hr_t, float), np.asarray(hr_v, float)
    res["hr"] = hr_res
    rest = _f(subject.get("resting_hr"))
    ref_max = float(subject["max_hr"]) if subject.get("max_hr") else hrmax
    res["hr_calc"] = {"age": age, "resting_hr": rest, "theoretical_hrmax": hrmax, "hrmax_formula": st.hrmax_formula,
                      "hrmax_is_estimate": True, "hr_reserve": hr_reserve(ref_max, rest) if ref_max else None,
                      "hrmax_used_for_zones": ref_max,
                      "karvonen": {f"{int(i * 100)}": karvonen(rest, ref_max, i) for i in (0.5, 0.6, 0.7, 0.8, 0.9)} if ref_max and rest else None,
                      "bmi": subject.get("bmi")}
    if hrmax is None and ref_max is None:
        warnings.append({"code": "NO_HRMAX", "level": "info", "message": "Age or HRmax not provided: HR zones and training load are N/A."})

    # ---------------------------------------------------------------- zones, training
    prog("Calculating HR zones")
    zone = None
    if hr_v is not None and ref_max:
        zone = zone_distribution(hr_t, hr_v, ref_max, [tuple(z) for z in st.zones])
    res["zones"] = zone
    src_sum = s.summary or {}
    res["source_zone_durations_s"] = {f"zone_{i}": (float(src_sum[f"zone_{i}_duration"]) / 1000.0 if src_sum.get(f"zone_{i}_duration") is not None else None) for i in range(6)} if s.summary else None
    prog("Calculating training load")
    tl = {"source": None, "calculated": None}
    if s.summary:
        tl["source"] = {"training_load": _f(src_sum.get("training_load")), "training_intensity": _f(src_sum.get("training_intensity")),
                        "acute_load": _f(src_sum.get("acute_load")), "chronic_load": _f(src_sum.get("chronic_load")),
                        "acwr": _f(src_sum.get("acwr")), "exertion_level": src_sum.get("exertion_level"),
                        "note": src_sum.get("user_feedback_comment")}
    if hr_v is not None and ref_max and rest:
        tl["calculated"] = banister_trimp(hr_t, hr_v, rest, ref_max, (subject.get("gender") or None))
    elif hr_v is not None:
        warnings.append({"code": "NO_RESTING_HR", "level": "info", "message": "Resting HR not provided: application-calculated TRIMP is N/A."})
    res["training"] = tl

    # ---------------------------------------------------------------- movement
    prog("Calculating movement load")
    mv = {"available": False, "source": None, "calculated": None}
    if s.acc is not None and len(s.acc) > 1:
        a = s.acc.dropna(subset=["value"])
        at = (a.t_abs - t0).dt.total_seconds().values
        mv["available"] = True
        mv["calculated"] = movement_metrics(at, a.value.values)
        arrays["acc_t"], arrays["acc_v"] = at.astype(float), a.value.values.astype(float)
    if s.summary:
        mv["source"] = {"movement_load": _f(src_sum.get("movement_load")), "movement_intensity": _f(src_sum.get("movement_intensity"))}
    res["movement"] = mv

    # ---------------------------------------------------------------- source vs calculated
    cmp = {}
    if s.summary and hr_v is not None:
        for k, c in (("avg_hr", hr_res.get("avg")), ("max_hr", hr_res.get("max")), ("min_hr", hr_res.get("min"))):
            sv = _f(src_sum.get(k))
            cmp[k] = {"source": sv, "calculated": c, "difference": (c - sv) if (sv is not None and c is not None) else None}
    if s.summary and mv["calculated"]:
        for k, ck in (("movement_load", "load"), ("movement_intensity", "intensity")):
            sv = _f(src_sum.get(k)); c = mv["calculated"][ck]
            cmp[k] = {"source": sv, "calculated": c, "difference": (c - sv) if (sv is not None and c is not None) else None}
    res["source_vs_calculated"] = cmp
    res["source_summary"] = _clean(s.summary) if s.summary else None
    prog("Generating visualizations")
    res["warnings"] = warnings
    res["status"] = "complete"
    rr_out = {}
    if n_rr:
        rr_out = {c: rr_tab[c].to_numpy() for c in ["t_s", "rr_ms", "hr_bpm", "segment", "artifact", "reason", "rr_corrected_ms", "status"]}
    return _clean(res), arrays, rr_out
