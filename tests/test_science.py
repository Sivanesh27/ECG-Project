"""Known-answer tests for the scientific core (no database / web server needed)."""
import io, zipfile
import numpy as np
import pandas as pd
import pytest

from app.analysis.ingestion.parser import IngestError, build_simple_csv, detect_sessions, safe_zip_members
from app.analysis.ecg.filtering import filter_ecg
from app.analysis.ecg.peaks import detect_r_peaks
from app.analysis.ecg.artifacts import ArtifactConfig, detect_artifacts, correct_rr
from app.analysis.ecg.rr import build_rr_table
from app.analysis.hrv.time_domain import time_domain
from app.analysis.hrv.frequency_domain import FreqConfig, frequency_domain
from app.analysis.training.hr_zones import theoretical_hrmax, zone_distribution, karvonen
from app.analysis.training.trimp import banister_trimp
from app.analysis.movement.movement_load import movement_metrics


def synth_ecg(fs=256, dur=60, hr=60, noise=0.02, seed=1):
    rng = np.random.default_rng(seed)
    t = np.arange(int(fs * dur)) / fs
    beat_t = np.arange(0.5, dur - 0.5, 60.0 / hr)
    x = np.zeros_like(t)
    for b in beat_t:
        x += np.exp(-((t - b) ** 2) / (2 * 0.012 ** 2))              # R
        x += 0.25 * np.exp(-((t - b - 0.25) ** 2) / (2 * 0.04 ** 2))  # T
    x += 0.3 * np.sin(2 * np.pi * 0.2 * t) + noise * rng.standard_normal(len(t))
    return t, x, beat_t


# ---------------- time domain
def test_time_domain_known_values():
    rr = np.array([800, 810, 790, 805, 795] * 10, float)
    r = time_domain([rr])
    d = np.diff(rr)
    assert r["rmssd"] == pytest.approx(np.sqrt(np.mean(d ** 2)))
    assert r["sdnn"] == pytest.approx(np.std(rr, ddof=1))
    assert r["nn50"] == 0 and r["pnn50"] == 0
    assert r["nn20"] == 0 and r["pnn20"] == 0
    assert r["mean_hr"] == pytest.approx(np.mean(60000 / rr))


def test_pnn50_and_pnn20():
    rr = np.array([800, 870, 800, 870] * 10, float)   # |d| = 70 always
    r = time_domain([rr])
    assert r["pnn50"] == 100 and r["pnn20"] == 100 and r["nn50"] == len(rr) - 1


def test_no_bridging_across_segments():
    a = np.full(40, 800.0); b = np.full(40, 1000.0)
    r = time_domain([a, b])
    assert r["rmssd"] == 0.0           # the 200 ms jump between segments must not count


def test_insufficient_data_is_none_not_zero():
    r = time_domain([np.array([800.0, 810.0, 790.0])])
    assert r["rmssd"] is None and r["sdnn"] is None


# ---------------- frequency domain
def _tach(f_hz, amp, dur, mean=900.0):
    t = [0.0]
    while t[-1] < dur:
        t.append(t[-1] + (mean + amp * np.sin(2 * np.pi * f_hz * t[-1])) / 1000.0)
    t = np.array(t[1:]); rr = mean + amp * np.sin(2 * np.pi * f_hz * t)
    return t, rr


def test_hf_dominates_for_025hz_oscillation():
    t, rr = _tach(0.25, 40, 200)
    r = frequency_domain([t], [rr])
    assert r["hf"] > 10 * r["lf"] and r["lf_hf"] < 0.2
    assert r["peak_hf_hz"] == pytest.approx(0.25, abs=0.03)
    assert r["hf"] == pytest.approx(40 ** 2 / 2, rel=0.25)       # variance of a sinusoid = A^2/2


def test_lf_dominates_for_01hz_oscillation_both_methods():
    t, rr = _tach(0.10, 30, 200)
    for m in ("welch", "lomb"):
        r = frequency_domain([t], [rr], FreqConfig(method=m))
        assert r["lf"] > 3 * r["hf"], m


def test_vlf_withheld_for_short_recording():
    t, rr = _tach(0.1, 30, 150)
    r = frequency_domain([t], [rr])
    assert r["vlf"] is None and r["total_power"] is None and r["lf"] is not None


def test_too_short_for_spectrum():
    t, rr = _tach(0.1, 30, 60)
    r = frequency_domain([t], [rr])
    assert r["lf"] is None and r["hf"] is None and r["notes"]


# ---------------- ECG / RR
def test_rpeak_detection_and_rr_generation():
    fs = 256
    t, x, beats = synth_ecg(fs=fs, dur=60, hr=75)
    y, info = filter_ecg(x, fs)
    p = detect_r_peaks(y, fs)
    assert abs(len(p) - len(beats)) <= 1
    tab = build_rr_table(t[p], np.zeros(len(p), int))
    assert tab.rr_ms.median() == pytest.approx(800, abs=8)
    assert tab.hr_bpm.median() == pytest.approx(75, abs=1)
    assert tab.artifact.mean() < 0.05


def test_powerline_notch_applies_when_present():
    fs = 512
    t, x, _ = synth_ecg(fs=fs, dur=30)
    x = x + 0.8 * np.sin(2 * np.pi * 50 * t)
    _, info = filter_ecg(x, fs)
    assert info["notch_applied"] is True


def test_artifact_detection_and_correction_modes():
    rr = np.full(60, 800.0); rr[20] = 1600; rr[40] = 250; rr[45] = 400
    t = np.cumsum(rr) / 1000
    flag, reason = detect_artifacts(rr)
    assert flag[20] and flag[40] and flag[45] and flag.sum() == 3
    assert reason[40] == "range"
    interp = correct_rr(t, rr, flag, "interpolate")
    assert np.all(np.abs(interp[flag] - 800) < 5)
    rej = correct_rr(t, rr, flag, "reject")
    assert np.isnan(rej[flag]).all() and not np.isnan(rej[~flag]).any()
    assert np.array_equal(correct_rr(t, rr, flag, "keep"), rr)


def test_hr_trend_not_flagged_as_artifact():
    rr = np.linspace(900, 450, 200)        # exercise ramp
    flag, _ = detect_artifacts(rr)
    assert flag.sum() == 0


# ---------------- zones / training / movement
def test_hrmax_formulas():
    assert theoretical_hrmax(30, "220-age") == 190
    assert theoretical_hrmax(30, "208-0.7age") == pytest.approx(187)
    assert theoretical_hrmax(30, "custom", 200) == 200


def test_karvonen():
    assert karvonen(60, 190, 0.5) == 125


def test_zone_distribution_sums_and_gaps():
    t = np.arange(0, 600, 3.0); hr = np.full(len(t), 150.0)          # 150/200 = 75 % -> zone 3
    z = zone_distribution(t, hr, 200.0)
    assert z["zones"][3]["seconds"] == pytest.approx(600, abs=3)
    assert sum(zz["percent"] for zz in z["zones"]) == pytest.approx(100)
    t2 = np.array([0, 3, 6, 3000, 3003.0]); hr2 = np.full(5, 150.0)    # 49-minute hole must not count
    assert zone_distribution(t2, hr2, 200.0)["total_s"] < 40


def test_trimp_scales_with_intensity_and_duration():
    t = np.arange(0, 1800, 3.0)
    lo = banister_trimp(t, np.full(len(t), 120.0), 60, 190, "male")["trimp"]
    hi = banister_trimp(t, np.full(len(t), 170.0), 60, 190, "male")["trimp"]
    assert hi > 2 * lo > 0
    assert banister_trimp(t, np.full(len(t), 50.0), 60, 190)["trimp"] == 0.0
    assert banister_trimp(t, np.full(len(t), 120.0), None or 60, 50)["trimp"] is None


def test_movement_metrics():
    t = np.arange(0, 3600, 3.0); a = np.full(len(t), 10.0)
    m = movement_metrics(t, a)
    assert m["intensity"] == 10.0 and m["load"] == pytest.approx(10.0, rel=0.01)   # 10 units * 1 hour
    assert movement_metrics([0.0], [1.0])["load"] is None


# ---------------- parser
def _zip(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return b.getvalue()


def test_zip_path_traversal_rejected():
    with pytest.raises(IngestError):
        detect_sessions("x.zip", _zip({"../evil/hr.csv": "timestamp,data_item,value\n"}))


def test_corrupted_zip_and_unsupported_format():
    with pytest.raises(IngestError):
        detect_sessions("x.zip", b"not a zip")
    with pytest.raises(IngestError):
        detect_sessions("x.txt", b"abc")


def test_chunked_session_combines_chunks_and_detects_gap():
    fs = 100
    def chunk(n): return "sample_index,ecg_value,is_pulse\n" + "\n".join(f"{i},{i % 7},0" for i in range(n))
    idx = ("sno,chunk_id,chunk_start_time,snapshot_id\n"
           "0,a,20250101T000000000000,s\n1,b,20250101T000010000000,s\n2,c,20250101T000100000000,s\n")
    z = _zip({"Subj/20250101_000000/ecg/0.csv": chunk(1000), "Subj/20250101_000000/ecg/1.csv": chunk(1000),
              "Subj/20250101_000000/ecg/2.csv": chunk(500), "Subj/20250101_000000/index.csv": idx,
              "Subj/20250101_000000/hr.csv": "timestamp,data_item,value\n2025-01-01 00:00:00+00:00,hr,70\n"})
    s = detect_sessions("d.zip", z)[0]
    assert s.subject_hint == "Subj" and s.ecg_fs == 100.0 and len(s.ecg) == 2500
    assert s.ecg.t.is_monotonic_increasing and s.quality["n_segments"] == 2 and len(s.quality["gaps"]) == 1


def test_simple_csv_formats_and_errors():
    s = build_simple_csv("a.csv", "timestamp,rr\n" + "\n".join(f"{i},{800 + (i % 3) * 10}" for i in range(50)))
    assert s.rr_ms is not None and len(s.rr_ms) == 50
    with pytest.raises(IngestError):
        build_simple_csv("a.csv", "foo,bar\n1,2\n")
    with pytest.raises(IngestError, match="timestamp"):
        build_simple_csv("a.csv", "ecg\n" + "\n".join(["1"] * 200))
    d = build_simple_csv("a.csv", "time,hr\n0,70\n1,71\n1,71\n2,x\n3,72\n")
    assert len(d.hr) == 3 and any("duplicate" in w for w in d.warnings)
