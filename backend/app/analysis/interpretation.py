"""Rule-based, cautious interpretation. Never diagnoses. Returns a list of {metric, value, text, level}."""
from __future__ import annotations

DISCLAIMER = ("This is an analysis and research tool, not a medical device. It does not diagnose arrhythmia, cardiac or "
              "autonomic conditions. Interpret results in the context of recording duration, physiological state and "
              "measurement quality, and consult a qualified professional for health decisions.")


def _fmt(v, unit="", nd=1):
    return "N/A — insufficient valid data" if v is None else f"{v:.{nd}f} {unit}".strip()


def interpret(r: dict) -> list[dict]:
    out = []
    q = r.get("quality", {}); t = r.get("hrv_time", {}); f = r.get("hrv_freq", {}); rec = r.get("recording", {})
    status = q.get("status")
    if status == "POOR":
        out.append({"metric": "Signal quality", "level": "warn", "value": _fmt(q.get("signal_quality_pct"), "%"),
                    "text": "Signal quality is insufficient for reliable interpretation. HRV metrics may be withheld or unreliable."})
    elif status in ("GOOD", "ACCEPTABLE"):
        out.append({"metric": "Signal quality", "level": "ok", "value": _fmt(q.get("signal_quality_pct"), "%"),
                    "text": f"Signal quality was rated {status} based on the share of RR intervals passing artifact screening "
                            f"({_fmt(q.get('artifact_pct'), '%')} flagged)."})
    dur = rec.get("ecg_valid_duration_s") or 0
    if t.get("n_nn"):
        kind = "ultra-short-term (< 5 min)" if dur < 300 else "short-term (5 min – 24 h scale)"
        out.append({"metric": "Recording length", "level": "info", "value": f"{dur:.0f} s",
                    "text": f"The valid ECG covers {dur:.0f} s, so HRV here is {kind}. Values from different recording lengths are not directly comparable."})
    if t.get("rmssd") is not None:
        out.append({"metric": "RMSSD", "level": "info", "value": _fmt(t["rmssd"], "ms"),
                    "text": "RMSSD is a time-domain measure of short-term beat-to-beat variability. It is sensitive to heart rate, "
                            "posture, breathing and activity, so it should be read in the context of the recording conditions."})
    if t.get("sdnn") is not None:
        out.append({"metric": "SDNN", "level": "info", "value": _fmt(t["sdnn"], "ms"),
                    "text": "SDNN is the overall variability of NN intervals; its value depends strongly on recording duration "
                            "and, during exercise, largely reflects heart-rate changes."})
    if f.get("lf") is not None:
        out.append({"metric": "LF / HF", "level": "info", "value": _fmt(f.get("lf_hf"), "", 2),
                    "text": "LF and HF are band powers (0.04–0.15 Hz and 0.15–0.40 Hz). The LF/HF ratio should not be interpreted as a "
                            "direct measure of sympathetic/parasympathetic balance; breathing rate and many other factors influence it."})
    if f.get("vlf") is None and t.get("n_nn"):
        out.append({"metric": "VLF / Total power", "level": "info", "value": "N/A",
                    "text": "VLF and total power are not reported because the valid recording is shorter than 5 minutes."})
    hr = r.get("hr", {}); calc = r.get("hr_calc", {})
    if hr.get("avg") is not None and calc.get("theoretical_hrmax"):
        out.append({"metric": "Heart rate", "level": "info", "value": _fmt(hr["avg"], "bpm"),
                    "text": f"Average HR was {hr['avg']:.0f} bpm against an age-based theoretical HRmax of {calc['theoretical_hrmax']:.0f} bpm "
                            f"({calc['hrmax_formula']}). Age-based HRmax is a population estimate and can differ substantially from an individual's measured maximum."})
    tl = r.get("training", {})
    if tl.get("calculated") and tl["calculated"].get("trimp") is not None:
        out.append({"metric": "Training load", "level": "info", "value": _fmt(tl["calculated"]["trimp"], "TRIMP"),
                    "text": "Training load shown here is an application-calculated Banister TRIMP from heart rate. It is not the same scale as "
                            "the source device's training load."})
    out.append({"metric": "Scope", "level": "info", "value": "", "text": DISCLAIMER})
    return out
