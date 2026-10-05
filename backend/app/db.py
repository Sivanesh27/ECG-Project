"""MongoDB (Motor) connection + indexes. Every user-owned collection carries userId and is indexed on it."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .config import get_config

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None

USER_OWNED = ["subjects", "uploads", "sessions", "analyses", "ecg_data", "rr_intervals", "hr_data", "hrv_results",
              "training_results", "movement_results", "reports", "jobs"]


def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        c = get_config()
        _client = AsyncIOMotorClient(c.mongodb_uri, tz_aware=True)
        _db = _client[c.mongodb_db]
    return _db


def set_db(db) -> None:           # used by tests (mongomock-motor)
    global _db
    _db = db


async def ensure_indexes(db: AsyncIOMotorDatabase | None = None) -> None:
    db = db if db is not None else get_db()
    await db.users.create_index("email", unique=True)
    await db.subjects.create_index("userId")
    await db.uploads.create_index([("userId", 1), ("createdAt", -1)])
    await db.sessions.create_index([("userId", 1), ("createdAt", -1)])
    await db.sessions.create_index([("userId", 1), ("startTime", -1)])
    await db.analyses.create_index([("userId", 1), ("createdAt", -1)])
    await db.jobs.create_index([("userId", 1), ("createdAt", -1)])
    for name in ("ecg_data", "rr_intervals", "hr_data", "hrv_results", "training_results", "movement_results", "reports"):
        await db[name].create_index([("userId", 1), ("sessionId", 1)])
    await db.password_resets.create_index("expiresAt", expireAfterSeconds=0)
