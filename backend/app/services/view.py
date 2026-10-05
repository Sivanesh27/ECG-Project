"""Read-side helpers: assemble an owner-scoped analysis context; build exports."""
from __future__ import annotations
import csv, io, json
import pandas as pd
from ..analysis.interpretation import interpret
from ..db import get_db
from .repo import by_session, owned_one, owned_session


def _strip(d):
    return {k: v for k, v in (d or {}).items() if k not in ("_id", "userId", "sessionId")}


async def assemble_context(user_id: str, sid: str, with_series: bool = True) -> dict:
    s = await owned_session(sid, user_id)
    subj = await get_db().subjects.find_one({"_id": s["subjectId"], "userId": user_id}) or {}
    an = _strip(await by_session("analyses", sid, user_id))
    hrv = _strip(await by_session("hrv_results", sid, user_id))
    tr = _strip(await by_session("training_results", sid, user_id))
    mv = _strip(await by_session("movement_results", sid, user_id))
    hd = _strip(await by_session("hr_data", sid, user_id))
    rr = _strip(await by_session("rr_intervals", sid, user_id))
    hrv_nl = hrv.get("nonlinear")
    flat = {"quality": an.get("quality", {}), "hrv_time": hrv.get("time", {}), "hrv_freq": hrv.get("frequency", {}),
            "hr": hd.get("stats", {}), "hr_calc": an.get("hr_calc", {}), "recording": an.get("recording", {}),
            "training": tr.get("training", {}), "movement": mv.get("movement", {})}
    ctx = {"session": _strip(s) | {"id": s["_id"]}, "subject": _strip(subj) | {"id": subj.get("_id")}, "analysis": an, "hrv": hrv,
           "training_results": tr, "movement_results": mv, "hr_series_stats": hd.get("stats", {}), "interpretation": interpret(flat),
           "hrv_nonlinear": hrv_nl}
    if with_series:
        ctx["hr_series"] = {k: hd.get(k) for k in ("t", "v", "acc_t", "acc_v")}
        ctx["rr"] = rr
    return ctx


def export_rr_csv(ctx: dict) -> str:
    rr = ctx.get("rr") or {}
    start = (ctx["analysis"].get("recording") or {}).get("ecg_start_time")
    base = pd.to_datetime(start, utc=True) if start else None
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["timestamp", "hr_bpm", "rr_ms", "artifact_flag", "corrected_rr_ms"])
    for i, t in enumerate(rr.get("t_s", [])):
        ts = (base + pd.to_timedelta(t, unit="s")).isoformat() if base is not None else f"{t:.3f}"
        w.writerow([ts, _r(rr["hr_bpm"][i], 2), _r(rr["rr_ms"][i], 1), int(rr["artifact"][i]), _r(rr["rr_corrected_ms"][i], 1)])
    return out.getvalue()


def export_hr_csv(ctx: dict) -> str:
    h = ctx.get("hr_series") or {}
    start = ctx["session"].get("startTime")
    base = pd.to_datetime(start, utc=True) if start else None
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["timestamp", "hr_bpm"])
    for t, v in zip(h.get("t") or [], h.get("v") or []):
        w.writerow([(base + pd.to_timedelta(t, unit="s")).isoformat() if base is not None else f"{t:.2f}", _r(v, 2)])
    return out.getvalue()


def export_summary(ctx: dict) -> dict:
    t, f = ctx["hrv"].get("time") or {}, ctx["hrv"].get("frequency") or {}
    hr = ctx["hr_series_stats"]; tr = (ctx["training_results"].get("training") or {})
    mv = (ctx["movement_results"].get("movement") or {})
    z = (ctx["training_results"].get("zones") or {}).get("zones") or []
    return {"session": ctx["session"].get("sessionName"), "subject": ctx["subject"].get("name"),
            "mean_hr": hr.get("avg"), "min_hr": hr.get("min"), "max_hr": hr.get("max"), "median_hr": hr.get("median"),
            "sdnn_ms": t.get("sdnn"), "rmssd_ms": t.get("rmssd"), "pnn50_pct": t.get("pnn50"), "pnn20_pct": t.get("pnn20"),
            "vlf_ms2": f.get("vlf"), "lf_ms2": f.get("lf"), "hf_ms2": f.get("hf"), "lf_hf": f.get("lf_hf"), "total_power_ms2": f.get("total_power"),
            "training_load_source": (tr.get("source") or {}).get("training_load"), "training_load_calculated_trimp": (tr.get("calculated") or {}).get("trimp"),
            "movement_load_source": (mv.get("source") or {}).get("movement_load"), "movement_load_calculated": (mv.get("calculated") or {}).get("load"),
            "zone_durations_s": {z_["label"]: z_["seconds"] for z_ in z}, "signal_quality": ctx["analysis"].get("quality", {}).get("status")}


def export_json(ctx: dict) -> str:
    slim = {k: v for k, v in ctx.items() if k not in ("rr", "hr_series")}
    slim["summary"] = export_summary(ctx)
    return json.dumps(slim, default=str, indent=1)


def _r(v, n):
    return "" if v is None else round(v, n)
