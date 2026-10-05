"""API tests: authentication, authorization, USER ISOLATION (mandatory), upload -> process -> results.
Needs: pip install -r backend/requirements.txt   (uses mongomock-motor; no real MongoDB required)."""
import asyncio
import pytest
from conftest import PASSWORD, Api, make_session_zip, register

pytestmark = pytest.mark.anyio

SUBJECT = {"name": "Alice Test", "age": 30, "gender": "female", "height_cm": 170, "weight_kg": 65, "resting_hr": 60}


async def upload_and_process(api: Api):
    z = make_session_zip()
    r = await api.req("POST", "/uploads", files={"file": ("data.zip", z, "application/zip")})
    assert r.status_code == 201, r.text
    up = r.json()
    assert up["summary"]["sessions"] == 1 and up["sessions"][0]["availability"]["ecg"] and up["sessions"][0]["ecg_fs_hz"] == 100.0
    r = await api.req("POST", "/analysis/process", json={"upload_id": up["id"], "subject": SUBJECT, "session_keys": [up["sessions"][0]["key"]]})
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    for _ in range(50):
        j = (await api.req("GET", f"/analysis/jobs/{jid}")).json()
        if j["status"] in ("complete", "error"):
            break
        await asyncio.sleep(0.1)
    assert j["status"] == "complete", j
    return up, j["sessionIds"][0]


# ------------------------------------------------------------------ authentication
async def test_register_login_logout_and_password_hashing(app_client):
    api = await register(app_client, "a@example.com")
    assert (await api.req("GET", "/auth/me")).json()["email"] == "a@example.com"
    from app.db import get_db
    u = await get_db().users.find_one({"email": "a@example.com"})
    assert u["password_hash"].startswith("$argon2") and PASSWORD not in str(u)
    cookie = [h for h in (await api.req("POST", "/auth/login", json={"email": "a@example.com", "password": PASSWORD})).headers.get_list("set-cookie") if "ecg_session" in h][0]
    assert "HttpOnly" in cookie
    assert (await api.req("POST", "/auth/logout")).status_code == 200
    api.c.cookies.clear()
    assert (await api.req("GET", "/auth/me")).status_code == 401


async def test_registration_validation(app_client):
    c = Api(app_client())
    weak = await c.req("POST", "/auth/register", json={"name": "Bob", "email": "b@example.com", "password": "short", "confirm_password": "short"})
    assert weak.status_code == 422
    mism = await c.req("POST", "/auth/register", json={"name": "Bob", "email": "b@example.com", "password": PASSWORD, "confirm_password": PASSWORD + "x"})
    assert mism.status_code == 422
    await register(app_client, "dup@example.com")
    dup = await c.req("POST", "/auth/register", json={"name": "Bob", "email": "DUP@example.com", "password": PASSWORD, "confirm_password": PASSWORD})
    assert dup.status_code == 409


async def test_wrong_password_and_unknown_user_same_error(app_client):
    await register(app_client, "x@example.com")
    c = Api(app_client())
    a = await c.req("POST", "/auth/login", json={"email": "x@example.com", "password": "Wrong-Passw0rd!"})
    b = await c.req("POST", "/auth/login", json={"email": "nobody@example.com", "password": "Wrong-Passw0rd!"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


async def test_unauthenticated_requests_rejected(app_client):
    c = Api(app_client())
    for m, u in (("GET", "/sessions"), ("GET", "/dashboard"), ("POST", "/uploads"), ("GET", "/analysis/abc"), ("DELETE", "/sessions/abc")):
        assert (await c.req(m, u)).status_code == 401


async def test_csrf_required_for_state_changing_requests(app_client):
    api = await register(app_client, "csrf@example.com")
    r = await api.c.request("PUT", "/api/settings", json={})          # no X-CSRF-Token header
    assert r.status_code == 403


# ------------------------------------------------------------------ pipeline through the API
async def test_upload_process_and_read_results(app_client):
    api = await register(app_client, "alice@example.com")
    up, sid = await upload_and_process(api)
    a = (await api.req("GET", f"/analysis/{sid}")).json()
    assert a["analysis"]["quality"]["status"] in ("GOOD", "ACCEPTABLE")
    assert a["hrv"]["time"]["rmssd"] is not None
    assert a["subject"]["bmi"] == 22.5
    ecg = (await api.req("GET", f"/analysis/{sid}/ecg?max_points=1000")).json()
    assert len(ecg["t"]) <= 1100 and ecg["downsampled"] and ecg["n_total"] == 15000
    assert (await api.req("GET", f"/analysis/{sid}/report")).content[:4] == b"%PDF"
    csv_text = (await api.req("GET", f"/analysis/{sid}/export?kind=rr")).text
    assert csv_text.splitlines()[0] == "timestamp,hr_bpm,rr_ms,artifact_flag,corrected_rr_ms"
    lst = (await api.req("GET", "/sessions")).json()
    assert lst["total"] == 1


async def test_bad_files_return_useful_errors(app_client):
    api = await register(app_client, "bad@example.com")
    r = await api.req("POST", "/uploads", files={"file": ("x.exe", b"MZ...", "application/octet-stream")})
    assert r.status_code == 415
    r = await api.req("POST", "/uploads", files={"file": ("x.zip", b"this is not a zip", "application/zip")})
    assert r.status_code == 415
    r = await api.req("POST", "/uploads", files={"file": ("x.csv", b"foo,bar\n1,2\n", "text/csv")})
    assert r.status_code == 422 and "Unsupported CSV columns" in r.json()["detail"]


async def test_delete_session_removes_data_and_files(app_client):
    api = await register(app_client, "del@example.com")
    _, sid = await upload_and_process(api)
    assert (await api.req("DELETE", f"/sessions/{sid}")).status_code == 200
    assert (await api.req("GET", f"/analysis/{sid}")).status_code == 404
    from app.db import get_db
    for coll in ("hrv_results", "rr_intervals", "hr_data", "ecg_data", "analyses"):
        assert await get_db()[coll].count_documents({"sessionId": sid}) == 0


# ------------------------------------------------------------------ MANDATORY: user isolation
async def test_user_b_cannot_access_user_a_data(app_client):
    """User A uploads a dataset; User B logs in and must not be able to see or touch ANY of it."""
    a = await register(app_client, "usera@example.com", "User A")
    up, sid = await upload_and_process(a)
    jobs = (await a.req("GET", "/sessions")).json()["items"]
    assert len(jobs) == 1
    b = await register(app_client, "userb@example.com", "User B")

    # lists are empty for B
    assert (await b.req("GET", "/sessions")).json() == {"items": [], "total": 0}
    assert (await b.req("GET", "/uploads")).json() == []
    d = (await b.req("GET", "/dashboard")).json()
    assert d["total_sessions"] == 0 and d["recent"] == []

    # every by-id endpoint answers 404 (same as non-existent: existence is not leaked)
    for path in (f"/analysis/{sid}", f"/analysis/{sid}/ecg", f"/analysis/{sid}/rr", f"/analysis/{sid}/hr", f"/analysis/{sid}/hrv",
                 f"/analysis/{sid}/training", f"/analysis/{sid}/movement", f"/analysis/{sid}/report", f"/analysis/{sid}/export?kind=json",
                 f"/analysis/{sid}/export?kind=rr", f"/uploads/{up['id']}"):
        r = await b.req("GET", path)
        assert r.status_code == 404, (path, r.status_code)
    assert (await b.req("DELETE", f"/sessions/{sid}")).status_code == 404
    assert (await b.req("DELETE", f"/uploads/{up['id']}")).status_code == 404
    assert (await b.req("POST", f"/analysis/{sid}/reprocess")).status_code == 404
    r = await b.req("POST", "/analysis/process", json={"upload_id": up["id"], "subject": SUBJECT, "session_keys": [up["sessions"][0]["key"]]})
    assert r.status_code == 404
    # B cannot read A's processing job either
    from app.db import get_db
    j = await get_db().jobs.find_one({"userId": {"$exists": True}})
    assert (await b.req("GET", f"/analysis/jobs/{j['_id']}")).status_code == 404

    # ...and A still has everything (B's delete attempts did nothing)
    assert (await a.req("GET", f"/analysis/{sid}")).status_code == 200
    assert (await a.req("GET", f"/analysis/{sid}/ecg")).status_code == 200


async def test_user_id_in_request_body_is_ignored(app_client):
    a = await register(app_client, "own1@example.com")
    await upload_and_process(a)
    b = await register(app_client, "own2@example.com")
    from app.db import get_db
    victim = (await get_db().users.find_one({"email": "own1@example.com"}))["_id"]
    z = make_session_zip()
    r = await b.req("POST", "/uploads?userId=" + victim, data={"userId": victim}, files={"file": ("d.zip", z, "application/zip")})
    assert r.status_code == 201
    up = await get_db().uploads.find_one({"_id": r.json()["id"]})
    assert up["userId"] != victim


async def test_storage_files_not_reachable_by_url(app_client):
    a = await register(app_client, "files@example.com")
    up, sid = await upload_and_process(a)
    for p in ("/storage/", "/api/storage/", "/uploads/original.zip", "/static/"):
        assert (await a.c.get(p)).status_code in (401, 404, 405)


async def test_delete_account_removes_everything(app_client):
    a = await register(app_client, "gone@example.com")
    await upload_and_process(a)
    r = await a.req("DELETE", "/auth/me", json={"password": PASSWORD})
    assert r.status_code == 200
    from app.db import get_db
    for coll in ("users", "sessions", "uploads", "subjects", "hrv_results", "rr_intervals", "jobs"):
        assert await get_db()[coll].count_documents({}) == 0, coll
