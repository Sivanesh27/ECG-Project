import asyncio
from typing import Literal, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from ..analysis.ecg_view import ecg_window
from ..analysis.hrv.metadata import METRICS
from ..db import get_db
from ..deps import current_user
from ..reports.report_generator import build_pdf
from ..schemas import SettingsIn
from ..services import processing, view
from ..services.repo import by_session, delete_session_data, load_ecg_arrays, new_id, now, owned_session

router = APIRouter(tags=["analysis"])


def _iso(x):
    return x.isoformat() if hasattr(x, "isoformat") else x


def _session_row(s: dict) -> dict:
    return {"id": s["_id"], "name": s["sessionName"], "subjectId": s["subjectId"], "subject": s["subjectName"], "start": _iso(s.get("startTime")),
            "end": _iso(s.get("endTime")), "durationS": s.get("durationS"), "quality": s.get("quality"), "availability": s.get("availability"),
            "summary": s.get("summary"), "createdAt": _iso(s.get("createdAt"))}


@router.get("/dashboard")
async def dashboard(user: dict = Depends(current_user)):
    db = get_db(); uid = user["_id"]
    total = await db.sessions.count_documents({"userId": uid})
    recent = await db.sessions.find({"userId": uid}).sort("startTime", -1).limit(8).to_list(8)
    rows = [_session_row(s) for s in recent]
    sm = [r["summary"] or {} for r in rows]
    def avg(k):
        v = [x[k] for x in sm if x.get(k) is not None]
        return sum(v) / len(v) if v else None
    latest = rows[0] if rows else None
    return {"total_sessions": total, "recent": rows, "latest": latest, "average_hr_recent": avg("avg_hr"),
            "kpis": {"latest_hr": (latest or {}).get("summary", {}).get("avg_hr"), "latest_rmssd": (latest or {}).get("summary", {}).get("rmssd"),
                     "latest_training_load": ((latest or {}).get("summary") or {}).get("training_load_source") if latest else None,
                     "latest_movement_load": ((latest or {}).get("summary") or {}).get("movement_load") if latest else None,
                     "latest_quality": (latest or {}).get("quality")}}


@router.get("/sessions")
async def list_sessions(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), user: dict = Depends(current_user)):
    cur = get_db().sessions.find({"userId": user["_id"]}).sort("startTime", -1).skip(skip).limit(limit)
    return {"items": [_session_row(s) for s in await cur.to_list(limit)],
            "total": await get_db().sessions.count_documents({"userId": user["_id"]})}


@router.delete("/sessions/{session_id}")
async def remove_session(session_id: str, user: dict = Depends(current_user)):
    await delete_session_data(session_id, user["_id"])
    return {"ok": True}


@router.get("/analysis/{session_id}")
async def get_analysis(session_id: str, user: dict = Depends(current_user)):
    ctx = await view.assemble_context(user["_id"], session_id, with_series=False)
    ctx["metric_metadata"] = METRICS
    ctx["session"] = {k: _iso(v) for k, v in ctx["session"].items()}
    ctx["subject"] = {k: _iso(v) for k, v in ctx["subject"].items()}
    return ctx


@router.get("/analysis/{session_id}/ecg")
async def get_ecg(session_id: str, t0: Optional[float] = None, t1: Optional[float] = None,
                  max_points: int = Query(8000, ge=500, le=20000), user: dict = Depends(current_user)):
    arrays = await load_ecg_arrays(session_id, user["_id"])
    return await asyncio.to_thread(ecg_window, arrays, t0, t1, max_points)


@router.get("/analysis/{session_id}/rr")
async def get_rr(session_id: str, user: dict = Depends(current_user)):
    await owned_session(session_id, user["_id"])
    d = await by_session("rr_intervals", session_id, user["_id"]) or {}
    return {k: v for k, v in d.items() if k not in ("_id", "userId", "sessionId")}


@router.get("/analysis/{session_id}/hr")
async def get_hr(session_id: str, user: dict = Depends(current_user)):
    await owned_session(session_id, user["_id"])
    d = await by_session("hr_data", session_id, user["_id"]) or {}
    t = await by_session("training_results", session_id, user["_id"]) or {}
    a = await by_session("analyses", session_id, user["_id"]) or {}
    return {**{k: v for k, v in d.items() if k not in ("_id", "userId", "sessionId")}, "zones": t.get("zones"), "hr_calc": a.get("hr_calc"),
            "source_vs_calculated": a.get("source_vs_calculated")}


@router.get("/analysis/{session_id}/hrv")
async def get_hrv(session_id: str, user: dict = Depends(current_user)):
    await owned_session(session_id, user["_id"])
    d = await by_session("hrv_results", session_id, user["_id"]) or {}
    a = await by_session("analyses", session_id, user["_id"]) or {}
    return {k: v for k, v in d.items() if k not in ("_id", "userId", "sessionId")} | {"quality": a.get("quality"), "recording": a.get("recording"),
            "warnings": a.get("warnings"), "metric_metadata": METRICS}


@router.get("/analysis/{session_id}/training")
async def get_training(session_id: str, user: dict = Depends(current_user)):
    await owned_session(session_id, user["_id"])
    d = await by_session("training_results", session_id, user["_id"]) or {}
    return {k: v for k, v in d.items() if k not in ("_id", "userId", "sessionId")}


@router.get("/analysis/{session_id}/movement")
async def get_movement(session_id: str, user: dict = Depends(current_user)):
    await owned_session(session_id, user["_id"])
    d = await by_session("movement_results", session_id, user["_id"]) or {}
    h = await by_session("hr_data", session_id, user["_id"]) or {}
    return {"movement": d.get("movement"), "t": h.get("acc_t"), "v": h.get("acc_v")}


@router.get("/analysis/{session_id}/report")
async def get_report(session_id: str, user: dict = Depends(current_user)):
    ctx = await view.assemble_context(user["_id"], session_id)
    pdf = await asyncio.to_thread(build_pdf, ctx)
    await get_db().reports.insert_one({"_id": new_id(), "userId": user["_id"], "sessionId": session_id, "format": "pdf", "createdAt": now()})
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="report_{session_id[:8]}.pdf"',
                                                                  "Cache-Control": "no-store"})


@router.get("/analysis/{session_id}/export")
async def export(session_id: str, kind: Literal["rr", "hr", "summary", "json"] = "rr", user: dict = Depends(current_user)):
    import csv, io
    ctx = await view.assemble_context(user["_id"], session_id)
    if kind == "rr":
        body, mt, ext = view.export_rr_csv(ctx), "text/csv", "csv"
    elif kind == "hr":
        body, mt, ext = view.export_hr_csv(ctx), "text/csv", "csv"
    elif kind == "summary":
        sm = view.export_summary(ctx); sm.pop("zone_durations_s", None)
        out = io.StringIO(); w = csv.writer(out); w.writerow(list(sm)); w.writerow(["" if v is None else v for v in sm.values()])
        body, mt, ext = out.getvalue(), "text/csv", "csv"
    else:
        body, mt, ext = view.export_json(ctx), "application/json", "json"
    return Response(body, media_type=mt, headers={"Content-Disposition": f'attachment; filename="{kind}_{session_id[:8]}.{ext}"', "Cache-Control": "no-store"})


@router.post("/analysis/{session_id}/reprocess", status_code=202)
async def reprocess(session_id: str, bg: BackgroundTasks, user: dict = Depends(current_user)):
    s = await owned_session(session_id, user["_id"])
    jid = await processing.create_job(user["_id"], "reprocess", {"upload_id": s["uploadId"], "subject_id": s["subjectId"], "session_keys": [s["sessionKey"]],
                                                                  "existing": {s["sessionKey"]: session_id}})
    bg.add_task(processing.run_job, jid, user["_id"])
    return {"job_id": jid, "status": "queued"}


@router.get("/settings")
async def get_settings(user: dict = Depends(current_user)):
    return SettingsIn(**(user.get("settings") or {})).model_dump()


@router.put("/settings")
async def put_settings(body: SettingsIn, user: dict = Depends(current_user)):
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": {"settings": body.model_dump()}})
    return body.model_dump()
