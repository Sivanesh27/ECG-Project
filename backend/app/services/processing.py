"""Background job: parse the stored ORIGINAL upload, analyse selected sessions, persist derived data separately."""
from __future__ import annotations
import asyncio, logging
import numpy as np
import pandas as pd
from ..analysis.ingestion.parser import IngestError, detect_sessions
from ..analysis.pipeline import STEPS, Settings, analyse_session
from ..db import get_db
from ..storage import get_storage
from .repo import bmi_info, new_id, now, npz_bytes

log = logging.getLogger("processing")
_sem = asyncio.Semaphore(2)          # at most 2 concurrent analyses per process


def settings_from_doc(d: dict | None) -> Settings:
    d = d or {}
    flt = dict(d.get("filter") or {}); flt.setdefault("powerline_hz", float(d.get("powerline_hz", 50)))
    return Settings(hrmax_formula=d.get("hrmax_formula", "220-age"), hrmax_custom=d.get("hrmax_custom"),
                    zones=d.get("zones") or Settings().zones, filter=flt, artifact=d.get("artifact") or {},
                    freq={k: tuple(v) if isinstance(v, list) else v for k, v in (d.get("freq") or {}).items()},
                    sampling_rate_override=d.get("sampling_rate_override"))


async def create_job(user_id: str, kind: str, payload: dict) -> str:
    jid = new_id()
    await get_db().jobs.insert_one({"_id": jid, "userId": user_id, "kind": kind, "status": "queued", "step": "Uploading",
                                    "stepIndex": 0, "steps": STEPS, "progress": 0.0, "sessionIds": [], "error": None,
                                    "payload": payload, "createdAt": now()})
    return jid


async def _set(jid, user_id, **kw):
    await get_db().jobs.update_one({"_id": jid, "userId": user_id}, {"$set": kw})


async def run_job(jid: str, user_id: str) -> None:
    db = get_db()
    loop = asyncio.get_running_loop()
    async with _sem:
        job = await db.jobs.find_one({"_id": jid, "userId": user_id})
        if not job:
            return
        try:
            await _set(jid, user_id, status="processing", step="Validating", stepIndex=1, progress=0.05)
            pl = job["payload"]
            up = await db.uploads.find_one({"_id": pl["upload_id"], "userId": user_id})
            if not up:
                raise IngestError("Upload not found.")
            user = await db.users.find_one({"_id": user_id})
            st = settings_from_doc(user.get("settings"))
            raw = get_storage().get(up["storageKey"])
            await _set(jid, user_id, step="Parsing", stepIndex=2, progress=0.15)
            sessions = await asyncio.to_thread(detect_sessions, up["filename"], raw, set(pl["session_keys"]) if up["filename"].lower().endswith(".zip") else None,
                                               st.sampling_rate_override)
            if not sessions:
                raise IngestError("None of the selected sessions could be found in the upload.")
            subject = await _ensure_subject(user_id, pl)
            ids = []
            for n, s in enumerate(sessions):
                base = 0.2 + 0.75 * n / len(sessions); span = 0.75 / len(sessions)

                def cb(step, base=base, span=span):
                    i = STEPS.index(step) if step in STEPS else 0
                    asyncio.run_coroutine_threadsafe(
                        _set(jid, user_id, step=step, stepIndex=i, progress=round(base + span * i / len(STEPS), 3)), loop)

                res, arrays, rr = await asyncio.to_thread(analyse_session, s, subject, st, cb)
                sid = (pl.get("existing") or {}).get(s.key) or new_id()
                await persist(user_id, sid, subject, up, s, res, arrays, rr)
                ids.append(sid)
            await _set(jid, user_id, status="complete", step="Complete", stepIndex=len(STEPS) - 1, progress=1.0, sessionIds=ids)
        except IngestError as e:
            await _set(jid, user_id, status="error", error=str(e))
        except Exception:                                    # noqa: BLE001  (never leak internals/data to client or logs)
            log.exception("analysis job failed (job=%s)", jid)
            await _set(jid, user_id, status="error", error="Analysis failed unexpectedly. The file may be malformed.")


async def _ensure_subject(user_id: str, pl: dict) -> dict:
    db = get_db()
    if pl.get("subject_id"):
        s = await db.subjects.find_one({"_id": pl["subject_id"], "userId": user_id})
        if s:
            return s
    s = dict(pl["subject"])
    s["_id"], s["userId"], s["createdAt"] = new_id(), user_id, now()
    s["bmi"], s["bmi_category"] = bmi_info(s.get("height_cm"), s.get("weight_kg"))
    s["resting_hr"], s["max_hr"] = s.get("resting_hr"), s.get("max_hr")
    await db.subjects.insert_one(s)
    pl["subject_id"] = s["_id"]
    return s


def _dt(x):
    return pd.to_datetime(x, utc=True).to_pydatetime() if x else None


def _decimate(t, v, n=20000):
    if len(t) <= n:
        return t, v
    idx = np.linspace(0, len(t) - 1, n).astype(int)
    return t[idx], v[idx]


async def persist(user_id, sid, subject, upload, s, res, arrays, rr) -> None:
    db = get_db(); store = get_storage()
    rec, q, hr = res["recording"], res["quality"], res["hr"]
    tl = (res["training"] or {})
    summary = {"avg_hr": hr.get("avg"), "max_hr": hr.get("max"), "min_hr": hr.get("min"),
               "rmssd": (res["hrv_time"] or {}).get("rmssd"), "pnn50": (res["hrv_time"] or {}).get("pnn50"),
               "training_load_source": (tl.get("source") or {}).get("training_load"),
               "training_load_calc": (tl.get("calculated") or {}).get("trimp"),
               "movement_load": ((res["movement"].get("source") or {}).get("movement_load")
                                 if res["movement"].get("source") else (res["movement"].get("calculated") or {}).get("load"))}
    existing = await db.sessions.find_one({"_id": sid, "userId": user_id}, {"createdAt": 1})
    doc = {"_id": sid, "userId": user_id, "subjectId": subject["_id"], "subjectName": subject["name"], "uploadId": upload["_id"],
           "sessionKey": s.key, "sessionName": s.name, "startTime": _dt(rec["start_time"]), "endTime": _dt(rec["end_time"]),
           "durationS": rec["session_duration_s"] or rec["ecg_valid_duration_s"], "quality": q.get("status"),
           "availability": rec["availability"], "summary": summary, "status": "complete",
           "createdAt": (existing or {}).get("createdAt") or now(), "updatedAt": now()}
    await db.sessions.replace_one({"_id": sid, "userId": user_id}, doc, upsert=True)
    base = {"userId": user_id, "sessionId": sid}
    meta = {k: res[k] for k in ("parameters", "warnings", "recording", "quality", "hr_calc", "source_vs_calculated", "source_summary", "ecg_processing") if k in res}
    await _put("analyses", base, {"status": "complete", "createdAt": now(), **meta})
    await _put("hrv_results", base, {"time": res["hrv_time"], "frequency": res["hrv_freq"], "nonlinear": res["hrv_nonlinear"]})
    await _put("training_results", base, {"training": res["training"], "zones": res["zones"], "source_zone_durations_s": res["source_zone_durations_s"]})
    await _put("movement_results", base, {"movement": res["movement"]})
    hd = {"stats": {k: v for k, v in hr.items()}}
    if "hr_t" in arrays:
        t, v = _decimate(arrays["hr_t"], arrays["hr_v"])
        hd.update(t=np.round(t, 2).tolist(), v=np.round(v, 2).tolist())
    if "acc_t" in arrays:
        t, v = _decimate(arrays["acc_t"], arrays["acc_v"])
        hd.update(acc_t=np.round(t, 2).tolist(), acc_v=np.round(v, 3).tolist())
    await _put("hr_data", base, hd)
    await _put("rr_intervals", base, {"n": int(len(rr.get("t_s", []))), **{k: _json_safe(v) for k, v in rr.items()}})
    if "ecg_t" in arrays:
        key = f"{user_id}/derived/{sid}/ecg.npz"
        store.put(key, npz_bytes({k: arrays[k] for k in ("ecg_t", "ecg_y", "ecg_seg", "peak_idx")}))
        await _put("ecg_data", base, {"storageKey": key, "fs": rec["ecg_fs_hz"], "n": rec["ecg_samples"]})
    else:
        await db.ecg_data.delete_many(base)


def _json_safe(v):
    """numpy array -> list with NaN/inf -> None (FastAPI's JSON encoder rejects NaN)."""
    a = v.tolist() if hasattr(v, "tolist") else v
    if isinstance(a, list) and a and isinstance(a[0], float):
        return [x if (x == x and abs(x) != float("inf")) else None for x in a]
    return a


async def _put(coll, base, body):
    body = {k: v for k, v in body.items() if k not in ("userId", "sessionId")}
    await get_db()[coll].update_one(base, {"$set": body, "$setOnInsert": {"_id": new_id()}}, upsert=True)
