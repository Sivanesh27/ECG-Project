# ECG / HRV Analytics

A multi-user web application for ECG, heart-rate, HRV, training-load and movement analysis.
**Stack:** FastAPI + NumPy/SciPy/Pandas (analysis) · MongoDB (metadata and results) · local or S3-compatible storage (raw files and ECG arrays) · React + TypeScript + Vite + Tailwind + Apache ECharts.

> Research and analysis tool, not a medical device. It never diagnoses; metrics that the data cannot support are shown as **N/A**, never as zero.

---

## 1. Run it locally

You need: **Python 3.11+**, **Node 18+**, and **MongoDB** (pick one option below).

### 1a. MongoDB (choose one)

```bash
# Option A - Docker (simplest)
docker run -d --name ecg-mongo -p 27017:27017 -v ecg_mongo:/data/db mongo:7

# Option B - MongoDB Atlas (free tier): create a cluster, add your IP, copy the connection string
#   and put it in MONGODB_URI in .env (see below)

# Option C - native install: https://www.mongodb.com/docs/manual/installation/  (then `mongod`)
```

### 1b. Configure

```bash
cd project
cp .env.example .env
# defaults work for local dev with Option A/C. For production generate a secret:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"      # -> JWT_SECRET
```

### 1c. Backend (terminal 1)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs (dev only): http://localhost:8000/docs · health check: http://localhost:8000/api/health

### 1d. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The dev server proxies `/api` to port 8000, so the session cookie is first-party.

### 1e. Try it with your dataset

1. Register an account → **Upload a recording**.
2. Enter subject details (age and resting HR enable zones and TRIMP) → upload `Dataset.zip`.
3. All detected sessions are listed with availability, sampling rate, gaps, etc. Select some (or the entire dataset) → **Analyse**.
4. Watch the 14-step progress, then explore Overview / ECG / RR / HR / HRV / Frequency / Training / Movement / Report.

Password reset has no SMTP yet: in development the reset link is printed in the backend console (`DEV_PRINT_RESET_LINKS=true`). Wire your email provider in `backend/app/api/auth.py` (`forgot`) for production.

### 1f. Whole stack in Docker

```bash
export JWT_SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")
docker compose up --build            # -> http://localhost:8080
```

---

## 2. Test it

```bash
cd project
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
pytest -v                                                         # science + API + isolation tests

# also run the checks against the real sample dataset:
DATASET_ZIP=/path/to/Dataset.zip pytest tests/test_real_dataset.py -v
```

| File | Covers |
|---|---|
| `tests/test_science.py` | ZIP/CSV parsing, timestamp/gap handling, path traversal, R-peak detection, RR, artifact modes, SDNN, RMSSD, pNN50/20, LF/HF/VLF (Welch and Lomb), HR zones, HRmax, Karvonen, TRIMP, movement |
| `tests/test_real_dataset.py` | All sessions parse and process; calculated vs source summary; ECG-derived HR vs device HR |
| `tests/test_api.py` | Registration/login/logout, Argon2, CSRF, validation, upload→process→results, deletion, **User A / User B isolation (mandatory)**, ownership ignoring body `userId`, account deletion |

`test_api.py` uses `mongomock-motor`, so no running MongoDB is needed for tests.

---

## 3. Deploy

| Part | Where | Notes |
|---|---|---|
| Database | **MongoDB Atlas** | Create a cluster, a DB user, allow your backend's IP, copy the SRV string to `MONGODB_URI`. |
| Backend | **Render / Railway / Fly / AWS** | Use `backend/Dockerfile`. Set the env vars below. |
| Files | **S3 / Cloudflare R2** | `STORAGE_BACKEND=s3` + `S3_*` vars. Bucket must be **private**; files are only served through authenticated API calls. |
| Frontend | **Vercel / Netlify** | Root dir `frontend`, build `npm run build`, output `dist`. |

**Render example (backend):** New Web Service → Docker → root dir `backend` → env vars → health check path `/api/health`.

**Production environment variables (backend):**

```
ENV=production
MONGODB_URI=mongodb+srv://...            MONGODB_DB=ecg_hrv
JWT_SECRET=<48+ random chars>            COOKIE_SECURE=true        COOKIE_SAMESITE=lax
CORS_ORIGINS=https://your-frontend.app   FRONTEND_URL=https://your-frontend.app
STORAGE_BACKEND=s3  S3_BUCKET=...  S3_ENDPOINT_URL=...  S3_ACCESS_KEY=...  S3_SECRET_KEY=...
```

**Frontend on Vercel:** edit `frontend/vercel.json` and replace `YOUR-BACKEND-HOST` with your backend host. The rewrite keeps `/api/*` same-origin, so the httpOnly cookie works without third-party-cookie problems. (Netlify: copy `public_redirects.txt` to `frontend/public/_redirects`.)

**Production checklist**
- HTTPS everywhere; `COOKIE_SECURE=true`.
- Private bucket; Atlas IP allow-list; unique `JWT_SECRET`.
- The rate limiter is in-process; use Redis (or a gateway) if you run several backend instances.
- The analysis job runner is in-process (`BackgroundTasks`, max 2 concurrent). For heavy multi-user load, move `services/processing.run_job` to a worker queue (Celery/RQ/Arq); the job document model already supports it.
- Add an email provider for password reset.
- Configure Atlas backups.

---

## 4. What the sample dataset actually looks like (parser is built on this)

Inspected from the supplied `Dataset.zip` (57 sessions, one subject folder):

- Session folder `YYYYMMDD_HHMMSS/` with `ecg/<n>.csv`, `index.csv`, `hr.csv`, `corrected_hr_avg.csv`, `hr_quality.csv`, `acc_rms_avg.csv`, `summary.csv`.
- **ECG chunks have no timestamps**: columns `sample_index, ecg_value, is_pulse` (15 000 samples per full chunk). Time comes from `index.csv` (`chunk_start_time`, format `YYYYmmddTHHMMSSffffff`). **The sampling rate is not stored anywhere**; it is estimated from chunk length ÷ spacing (≈ 29.295 s → **512 Hz**) and snapped to a standard rate.
- ECG is **intermittent snapshots** (typically ~2 min per session, sometimes with a long gap), not continuous across the session. HRV therefore describes the valid ECG windows only. RR intervals are never computed across gaps.
- `hr.csv` is on a 4 Hz grid but mostly empty; `corrected_hr_avg.csv` is 3-s averaged HR; `hr_quality.csv` every ~9 s; `acc_rms_avg.csv` 3-s accelerometer RMS.
- `summary.csv` is one wide row: `avg_hr, max_hr, min_hr, training_load, training_intensity, movement_load, movement_intensity, acute/chronic load, zone_0..5_duration` (**milliseconds**), etc.
- 4 sessions have no ECG and 8 have a single chunk (rate cannot be estimated → "UNKNOWN SAMPLING RATE"; set a sampling-rate override in Settings to include them).

Relations verified on the data and used as documented algorithms: `avg_hr`/`max_hr` equal the mean/max of `corrected_hr_avg`; `movement_intensity = mean(acc_rms_avg)`; `movement_load = Σ acc_rms·Δt / 3600`. Source values are always shown next to application-calculated ones with the difference.

## 5. Scientific methods (short)

| Step | Method |
|---|---|
| Filtering | Zero-phase Butterworth band-pass (default 0.5–40 Hz, configurable); 50 Hz (default) / 60 Hz notch applied only when powerline contamination is detected |
| R-peaks | Pan–Tompkins-style detector implemented in NumPy/SciPy (band-pass → derivative → squaring → moving integration → adaptive threshold → refinement, T-wave and amplitude pruning, search-back) |
| RR / artifacts | RR = Δt of successive R-peaks per continuous segment; flags: physiological range (300–2000 ms), local-median ratios (short/long/jump). Modes: interpolate (default) / reject / keep |
| Time domain | SDNN, RMSSD, SDSD, NN50/20, pNN50/20, CVNN, triangular index and TINN (≥ 200 NN). Successive differences never bridge rejected beats or gaps |
| Frequency | Welch on 4 Hz cubic-resampled, detrended tachogram (default) or Lomb–Scargle. LF/HF need ≥ 120 s valid data; **VLF and total power need ≥ 300 s** and are otherwise N/A |
| HR zones / HRmax | `220 − age` (default), `208 − 0.7·age`, or custom; zone time uses capped sample hold so gaps don't count |
| Training load | Banister TRIMP `Σ Δt·HRr·0.64·e^(b·HRr)`, shown beside (not replacing) the dataset's value |
| Metric catalogue | `backend/app/analysis/hrv/metadata.py` – inputs, minimum data, method, unit, limits |

## 6. Security and privacy summary

Argon2id password hashing · JWT in **httpOnly** cookie · CSRF (double-submit + Origin check) · CORS allow-list · rate limiting · strict input validation (Pydantic) · file-type/magic-byte/size checks · ZIP path-traversal and bomb protection · opaque UUID storage keys, files never served by URL · **every repository call is scoped by `userId` derived only from the cookie**; non-owned resources return 404 · NPZ loaded with `allow_pickle=False` · generic error messages, no bodies or tokens in logs · delete session / upload / account removes DB rows and stored files.


