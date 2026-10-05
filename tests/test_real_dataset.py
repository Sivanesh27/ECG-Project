"""Runs the full pipeline on the supplied sample dataset when available (set DATASET_ZIP)."""
import os
import numpy as np
import pytest
from app.analysis.ingestion.parser import detect_sessions
from app.analysis.pipeline import analyse_session, Settings

ZIP = os.environ.get("DATASET_ZIP", "")
pytestmark = pytest.mark.skipif(not os.path.exists(ZIP), reason="set DATASET_ZIP to the sample Dataset.zip")


@pytest.fixture(scope="module")
def sessions():
    return detect_sessions("Dataset.zip", open(ZIP, "rb").read())


def test_sessions_detected_and_generalised(sessions):
    assert len(sessions) >= 50 and all(s.subject_hint for s in sessions)
    with_ecg = [s for s in sessions if s.ecg is not None]
    assert with_ecg and all(s.ecg_fs == 512.0 for s in with_ecg)
    assert all(s.ecg.t.is_monotonic_increasing for s in with_ecg)


def test_every_session_processes_without_crashing(sessions):
    subj = dict(age=24, gender="male", resting_hr=60)
    for s in sessions:
        r, arrays, rr = analyse_session(s, subj, Settings())
        assert r["status"] == "complete"


def test_calculated_matches_source_summary(sessions):
    subj = dict(age=24, gender="male", resting_hr=60)
    for s in sessions[:15]:
        r, *_ = analyse_session(s, subj, Settings())
        c = r["source_vs_calculated"]
        assert abs(c["avg_hr"]["difference"]) < 0.05 and abs(c["movement_load"]["difference"]) < 0.01


def test_peak_detector_agrees_with_device_hr_series(sessions):
    """Independent validation: per continuous ECG segment (>= 60 s), ECG-derived mean HR vs the device's own
    corrected HR series over the same window. Expect a small median error and most segments within 10 %."""
    from app.analysis.ecg.filtering import filter_ecg
    from app.analysis.ecg.peaks import detect_r_peaks
    errs = []
    for s in [x for x in sessions if x.ecg is not None]:
        for seg, g in s.ecg.groupby("segment"):
            if len(g) < s.ecg_fs * 60:
                continue
            y, _ = filter_ecg(g.v.values, s.ecg_fs)
            p = detect_r_peaks(y, s.ecg_fs)
            if len(p) < 30:
                continue
            hr = 60.0 / (np.diff(p) / s.ecg_fs).mean()
            t0 = s.ecg_start + np.timedelta64(int(g.t.iloc[0] * 1000), "ms")
            t1 = t0 + np.timedelta64(int(len(g) / s.ecg_fs * 1000), "ms")
            c = s.corrected_hr[(s.corrected_hr.t_abs >= t0) & (s.corrected_hr.t_abs <= t1)].value
            if len(c) >= 15:
                errs.append(abs(hr - c.mean()) / c.mean() * 100)
    errs = np.array(errs)
    assert len(errs) >= 20
    assert np.median(errs) < 5 and (errs < 10).mean() > 0.85
