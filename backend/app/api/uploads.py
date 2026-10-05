import asyncio, hashlib, os, re
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from ..analysis.ingestion.parser import IngestError, detect_sessions
from ..config import get_config
from ..db import get_db
from ..deps import current_user
from ..schemas import ProcessIn
from ..security import client_ip, limiter
from ..services import processing
from ..services.repo import delete_upload, new_id, now, owned_one
from ..storage import get_storage

router = APIRouter(tags=["uploads"])
ALLOWED = {".zip": b"PK", ".xlsx": b"PK", ".csv": None}


def safe_name(n: str) -> str:
    n = os.path.basename((n or "upload").replace("\\", "/"))
    return re.sub(r"[^A-Za-z0-9._ \-()]", "_", n)[:120] or "upload"


def _iso(x):
    return x.isoformat() if x is not None and hasattr(x, "isoformat") else None


@router.post("/uploads", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), user: dict = Depends(current_user)):
    c = get_config()
    limiter.check("upload:" + user["_id"], c.rate_limit_upload_per_min)
    name = safe_name(file.filename)
    ext = os.path.splitext(name.lower())[1]
    if ext not in ALLOWED:
        raise HTTPException(415, "UNSUPPORTED FILE FORMAT: use .zip, .csv or .xlsx")
    chunks, size, limit = [], 0, c.max_upload_mb * 1024 * 1024
    while True:
        b = await file.read(1024 * 1024)
        if not b:
            break
        size += len(b)
        if size > limit:
            raise HTTPException(413, f"File exceeds the {c.max_upload_mb} MB limit")
        chunks.append(b)
    raw = b"".join(chunks)
    if not raw:
        raise HTTPException(422, "The file is empty")
    magic = ALLOWED[ext]
    if magic and not raw.startswith(magic):
        raise HTTPException(415, f"File content does not match the {ext} extension")
    if ext == ".csv" and b"\x00" in raw[:4096]:
        raise HTTPException(415, "File content is not text/CSV")
    try:
        sessions = await asyncio.to_thread(detect_sessions, name, raw)
    except IngestError as e:
        raise HTTPException(422, str(e))
    uid, upid = user["_id"], new_id()
    key = f"{uid}/uploads/{upid}/original{ext}"          # opaque, UUID-based, never user-influenced; original never modified
    get_storage().put(key, raw)
    det = []
    for s in sessions:
        dur = (s.end_time - s.start_time).total_seconds() if s.start_time is not None and s.end_time is not None else None
        det.append({"key": s.key, "name": s.name, "subject_hint": s.subject_hint, "start": _iso(s.start_time), "end": _iso(s.end_time),
                    "duration_s": dur, "availability": s.availability(), "ecg_fs_hz": s.ecg_fs, "fs_source": s.fs_source,
                    "ecg_samples": int(s.quality.get("samples", 0)), "missing_samples": int(s.quality.get("missing_samples", 0)),
                    "duplicate_samples": int(s.quality.get("duplicate_samples", 0)), "gaps": s.quality.get("gaps", []),
                    "n_chunks": s.quality.get("n_chunks"), "warnings": s.warnings})
    doc = {"_id": upid, "userId": uid, "filename": name, "size": size, "storageKey": key, "sha256": hashlib.sha256(raw).hexdigest(),
           "sessions": det, "createdAt": now()}
    await get_db().uploads.insert_one(doc)
    return {k: doc[k] for k in ("_id", "filename", "size", "sessions")} | {"id": upid, "createdAt": _iso(doc["createdAt"]),
            "summary": {"sessions": len(det), "with_ecg": sum(d["availability"]["ecg"] for d in det), "with_hr": sum(d["availability"]["hr"] for d in det),
                        "with_movement": sum(d["availability"]["movement"] for d in det), "with_summary": sum(d["availability"]["summary"] for d in det)}}


@router.get("/uploads")
async def list_uploads(user: dict = Depends(current_user)):
    docs = await get_db().uploads.find({"userId": user["_id"]}, {"storageKey": 0, "sessions": 0}).sort("createdAt", -1).to_list(200)
    return [{"id": d["_id"], "filename": d["filename"], "size": d["size"], "createdAt": _iso(d["createdAt"])} for d in docs]


@router.get("/uploads/{upload_id}")
async def get_upload(upload_id: str, user: dict = Depends(current_user)):
    d = await owned_one("uploads", upload_id, user["_id"], {"storageKey": 0})
    d["id"] = d.pop("_id"); d.pop("userId", None); d["createdAt"] = _iso(d["createdAt"])
    return d


@router.delete("/uploads/{upload_id}")
async def remove_upload(upload_id: str, user: dict = Depends(current_user)):
    await delete_upload(upload_id, user["_id"])
    return {"ok": True}


@router.post("/analysis/process", status_code=202)
async def process(body: ProcessIn, bg: BackgroundTasks, user: dict = Depends(current_user)):
    up = await owned_one("uploads", body.upload_id, user["_id"])
    valid = {s["key"] for s in up["sessions"]}
    if any(k not in valid for k in body.session_keys):
        raise HTTPException(422, "Unknown session selected")
    jid = await processing.create_job(user["_id"], "process", {"upload_id": up["_id"], "subject": body.subject.model_dump(), "session_keys": body.session_keys})
    bg.add_task(processing.run_job, jid, user["_id"])
    return {"job_id": jid, "status": "queued"}


@router.get("/analysis/jobs/{job_id}")
async def job(job_id: str, user: dict = Depends(current_user)):
    j = await owned_one("jobs", job_id, user["_id"])
    return {"job_id": j["_id"], "status": j["status"], "step": j["step"], "stepIndex": j["stepIndex"], "steps": j["steps"],
            "progress": j["progress"], "sessionIds": j.get("sessionIds", []), "error": j.get("error")}
