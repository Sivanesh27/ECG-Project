import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .api import analysis, auth, uploads
from .config import get_config
from .db import ensure_indexes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)       # no URLs/queries with identifiers in access logs


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_config()
    await ensure_indexes()
    yield


app = FastAPI(title="ECG/HRV Analytics API", version="1.0.0", lifespan=lifespan,
              docs_url=None if get_config().env == "production" else "/docs", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=get_config().origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                         "Cache-Control": resp.headers.get("Cache-Control", "no-store")})
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logging.getLogger("api").exception("unhandled error on %s %s", request.method, request.url.path)   # path only; no body/headers
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


for r in (auth.router, uploads.router, analysis.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
