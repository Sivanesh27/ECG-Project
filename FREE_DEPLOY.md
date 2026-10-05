# Free deployment (no card anywhere)

One Render free web service runs the API **and** the website (same origin, so no CORS/cookie/domain issues).
MongoDB Atlas M0 holds the data **and** the stored files (GridFS). No Vercel, R2 or S3 needed.

## 1. MongoDB Atlas (free M0, no card)
Create a free M0 cluster -> Database Access: add a user (letters+digits password) -> Network Access: add 0.0.0.0/0
-> Connect -> Drivers -> copy the `mongodb+srv://...` string.

## 2. Put the project on GitHub
Create a free GitHub account + a new **private** repo, then from D:\ecg project:
    git init
    git add .
    git commit -m "ECG HRV app"
    git branch -M main
    git remote add origin https://github.com/YOUR_NAME/ecg-hrv.git
    git push -u origin main
(.gitignore already keeps .env, .venv and node_modules out.)

## 3. Render (free web service)
New -> Web Service -> connect the repo -> Runtime: **Docker**, Root Directory: **(leave empty)**, Instance Type: **Free**.
Health Check Path: /api/health. Environment variables:

    ENV=production
    MONGODB_URI=<your Atlas string>
    MONGODB_DB=ecg_hrv
    JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
    COOKIE_SECURE=true
    STORAGE_BACKEND=mongo
    MAX_UPLOAD_MB=30
    CORS_ORIGINS=https://YOUR-SERVICE.onrender.com
    FRONTEND_URL=https://YOUR-SERVICE.onrender.com
    DEV_PRINT_RESET_LINKS=false

(The service URL is shown after you create it; add the two URL variables then and let it redeploy.)

## Free-tier behaviour
- Sleeps after ~15 min idle; first request afterwards takes about a minute.
- Jobs run inside the web process: a restart/sleep mid-analysis loses that job (just run it again).
- Password-reset e-mail is not implemented, so "forgot password" will not deliver a link in production.
- Atlas M0 is 512 MB: delete sessions/uploads you no longer need.
- `python tools/split_dataset.py Dataset.zip --sessions 12` splits a bigger dataset into several smaller ZIPs.

## No-card fallback: run on your own PC
Build the site once (`cd frontend; npm run build`), then
    $env:FRONTEND_DIST="D:\ecg project\frontend\dist"; cd backend; uvicorn app.main:app --port 8000
and open http://localhost:8000 . To share it temporarily, install Cloudflare's `cloudflared` and run
    cloudflared tunnel --url http://localhost:8000
(gives a temporary https URL, no account needed; the PC must stay on).
