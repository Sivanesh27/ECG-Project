"""Repository layer. EVERY function takes user_id and filters on it -- there is deliberately no way to fetch a
user-owned document without it. Non-owned and non-existent are indistinguishable (both 404)."""
from __future__ import annotations
import io, uuid
from datetime import datetime, timezone
import numpy as np
from fastapi import HTTPException
from ..db import get_db, USER_OWNED
from ..storage import get_storage

RESULT_COLLS = ["analyses", "ecg_data", "rr_intervals", "hr_data", "hrv_results", "training_results", "movement_results", "reports"]


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(timezone.utc)


def bmi_info(h_cm, w_kg):
    if not h_cm or not w_kg:
        return None, None
    b = w_kg / ((h_cm / 100) ** 2)
    cat = "Underweight range" if b < 18.5 else "Normal range" if b < 25 else "Overweight range" if b < 30 else "Obesity range"
    return round(b, 1), cat


async def owned_one(coll: str, doc_id: str, user_id: str, projection: dict | None = None) -> dict:
    doc = await get_db()[coll].find_one({"_id": doc_id, "userId": user_id}, projection)
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


async def owned_session(session_id: str, user_id: str) -> dict:
    return await owned_one("sessions", session_id, user_id)


async def by_session(coll: str, session_id: str, user_id: str) -> dict | None:
    return await get_db()[coll].find_one({"userId": user_id, "sessionId": session_id})


def npz_bytes(arrays: dict) -> bytes:
    b = io.BytesIO()
    np.savez_compressed(b, **arrays)
    return b.getvalue()


def load_npz(data: bytes) -> dict:
    with np.load(io.BytesIO(data), allow_pickle=False) as z:     # allow_pickle=False: never unpickle user-influenced data
        return {k: z[k] for k in z.files}


async def load_ecg_arrays(session_id: str, user_id: str) -> dict:
    d = await by_session("ecg_data", session_id, user_id)
    if not d or not d.get("storageKey"):
        raise HTTPException(404, "No ECG data for this session")
    return load_npz(get_storage().get(d["storageKey"]))


async def delete_session_data(session_id: str, user_id: str) -> None:
    db = get_db()
    await owned_session(session_id, user_id)
    get_storage().delete_prefix(f"{user_id}/derived/{session_id}")
    for c in RESULT_COLLS:
        await db[c].delete_many({"userId": user_id, "sessionId": session_id})
    await db.sessions.delete_one({"_id": session_id, "userId": user_id})


async def delete_upload(upload_id: str, user_id: str) -> None:
    db = get_db()
    up = await owned_one("uploads", upload_id, user_id)
    for s in await db.sessions.find({"userId": user_id, "uploadId": upload_id}, {"_id": 1}).to_list(None):
        await delete_session_data(s["_id"], user_id)
    get_storage().delete_prefix(f"{user_id}/uploads/{upload_id}")
    await db.uploads.delete_one({"_id": upload_id, "userId": user_id})


async def delete_user_everything(user_id: str) -> None:
    db = get_db()
    get_storage().delete_prefix(f"{user_id}")
    for c in USER_OWNED:
        await db[c].delete_many({"userId": user_id})
    await db.password_resets.delete_many({"userId": user_id})
    await db.users.delete_one({"_id": user_id})
