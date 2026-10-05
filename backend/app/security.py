import hmac, re, secrets, time, hashlib
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import HTTPException, Request

from .config import get_config

_ph = PasswordHasher()                # Argon2id, library defaults
_DUMMY = _ph.hash("dummy-password-for-timing")
SESSION_COOKIE, CSRF_COOKIE = "ecg_session", "csrf_token"


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str | None) -> bool:
    try:
        return _ph.verify(hashed or _DUMMY, pw) and hashed is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_problems(pw: str, email: str = "") -> list[str]:
    p = []
    if len(pw) < 10: p.append("at least 10 characters")
    if not re.search(r"[a-z]", pw): p.append("a lowercase letter")
    if not re.search(r"[A-Z]", pw): p.append("an uppercase letter")
    if not re.search(r"\d", pw): p.append("a digit")
    if email and email.split("@")[0].lower() in pw.lower() and len(email.split("@")[0]) >= 4: p.append("must not contain your email name")
    return p


def make_token(user_id: str, ver: int, remember: bool) -> tuple[str, int]:
    c = get_config()
    ttl = timedelta(days=c.remember_days) if remember else timedelta(hours=c.session_hours)
    now = datetime.now(timezone.utc)
    tok = jwt.encode({"sub": user_id, "ver": ver, "iat": now, "exp": now + ttl}, c.jwt_secret, algorithm=c.jwt_algorithm)
    return tok, int(ttl.total_seconds())


def decode_token(tok: str) -> dict | None:
    c = get_config()
    try:
        return jwt.decode(tok, c.jwt_secret, algorithms=[c.jwt_algorithm])
    except jwt.PyJWTError:
        return None


def new_csrf() -> str:
    return secrets.token_urlsafe(32)


def check_csrf(request: Request) -> None:
    """Double-submit cookie + Origin check for state-changing requests."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    c = get_config()
    origin = request.headers.get("origin")
    if origin and origin not in c.origins and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Origin not allowed")
    ck, hd = request.cookies.get(CSRF_COOKIE), request.headers.get("x-csrf-token")
    if not ck or not hd or not hmac.compare_digest(ck, hd):
        raise HTTPException(403, "CSRF validation failed")


def hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


class RateLimiter:
    """Small in-memory sliding-window limiter (single instance). Use Redis for multi-instance deployments."""
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str, limit: int, window: int = 60) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, "Too many requests. Please slow down.")
        q.append(now)


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?"))
