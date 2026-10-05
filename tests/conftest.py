import io, os, sys, tempfile, zipfile
import numpy as np
import pytest

os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-123")
os.environ.setdefault("STORAGE_DIR", tempfile.mkdtemp(prefix="ecg_test_storage_"))
os.environ.setdefault("RATE_LIMIT_AUTH_PER_MIN", "1000")
os.environ.setdefault("RATE_LIMIT_UPLOAD_PER_MIN", "1000")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def make_session_zip(subject="Test Subject", name="20250101_000000", n_chunks=5, fs=100, hr=72, seed=3) -> bytes:
    """Small synthetic device-style export (chunked ECG + index + hr + acc + summary), for tests only."""
    rng = np.random.default_rng(seed)
    n = fs * 30
    files = {}
    base = f"{subject}/{name}"
    rows = ["sno,chunk_id,chunk_start_time,snapshot_id"]
    for c in range(n_chunks):
        t = (np.arange(n) / fs) + c * 30
        x = np.zeros(n)
        for b in np.arange(0.4, 30, 60 / hr):
            x += 800 * np.exp(-((t - c * 30 - b) ** 2) / (2 * 0.012 ** 2)) + 150 * np.exp(-((t - c * 30 - b - 0.25) ** 2) / (2 * 0.04 ** 2))
        x += 5 * rng.standard_normal(n)
        files[f"{base}/ecg/{c}.csv"] = "sample_index,ecg_value,is_pulse\n" + "\n".join(f"{i},{int(v)},0" for i, v in enumerate(x))
        s = c * 30
        rows.append(f"{c},c{c},20250101T00{s // 60:02d}{s % 60:02d}000000,snap")
    files[f"{base}/index.csv"] = "\n".join(rows) + "\n"
    files[f"{base}/hr.csv"] = "timestamp,data_item,value\n" + "\n".join(
        f"2025-01-01 00:{i // 60:02d}:{i % 60:02d}+00:00,hr,{hr + (i % 5)}" for i in range(0, 150, 3)) + "\n"
    files[f"{base}/corrected_hr_avg.csv"] = files[f"{base}/hr.csv"].replace(",hr,", ",corrected_hr_avg,")
    files[f"{base}/acc_rms_avg.csv"] = "timestamp,data_item,value\n" + "\n".join(
        f"2025-01-01 00:{i // 60:02d}:{i % 60:02d}+00:00,acc_rms_avg,{i % 7}" for i in range(0, 150, 3)) + "\n"
    files[f"{base}/summary.csv"] = ("session_start_time,avg_hr,max_hr,min_hr,training_load,training_intensity,movement_load,movement_intensity\n"
                                    "2025-01-01T00:00:00+00:00,74,76,72,1.5,0.6,0.01,3\n")
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return b.getvalue()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def app_client():
    from mongomock_motor import AsyncMongoMockClient
    from app import db as dbmod
    from app.storage import LocalStorage, set_storage
    from httpx import ASGITransport, AsyncClient
    dbmod.set_db(AsyncMongoMockClient()["ecg_test"])
    await dbmod.ensure_indexes()
    set_storage(LocalStorage(tempfile.mkdtemp(prefix="ecg_store_")))
    from app.main import app

    def make():
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return make


class Api:
    """Thin helper: keeps cookies per user and adds the CSRF header automatically."""
    def __init__(self, client):
        self.c = client

    async def req(self, method, url, **kw):
        h = kw.pop("headers", {})
        tok = self.c.cookies.get("csrf_token")
        if tok:
            h["X-CSRF-Token"] = tok
        return await self.c.request(method, "/api" + url, headers=h, **kw)


PASSWORD = "Str0ng-Passw0rd!"


async def register(make, email, name="User"):
    cl = make()
    api = Api(cl)
    r = await api.req("POST", "/auth/register", json={"name": name, "email": email, "password": PASSWORD, "confirm_password": PASSWORD})
    assert r.status_code == 201, r.text
    return api
