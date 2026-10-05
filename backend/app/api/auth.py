import logging, secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError
from ..config import get_config
from ..db import get_db
from ..deps import current_user
from ..schemas import DeleteAccountIn, ForgotIn, LoginIn, RegisterIn, ResetIn
from ..security import (CSRF_COOKIE, SESSION_COOKIE, client_ip, hash_password, hash_token, limiter, make_token, new_csrf,
                        password_problems, verify_password)
from ..services.repo import delete_user_everything, new_id, now

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("auth")


def _public(u: dict) -> dict:
    return {"id": u["_id"], "name": u["name"], "email": u["email"], "organization": u.get("organization"), "role": u.get("role"),
            "createdAt": u.get("createdAt")}


def _set_cookies(resp: Response, user: dict, remember: bool):
    c = get_config()
    tok, ttl = make_token(user["_id"], user.get("tokenVersion", 0), remember)
    kw = dict(secure=c.cookie_secure, samesite=c.cookie_samesite, path="/")
    resp.set_cookie(SESSION_COOKIE, tok, httponly=True, max_age=ttl if remember else None, **kw)
    resp.set_cookie(CSRF_COOKIE, new_csrf(), httponly=False, max_age=ttl if remember else None, **kw)


@router.post("/register", status_code=201)
async def register(body: RegisterIn, request: Request, response: Response):
    limiter.check("auth:" + client_ip(request), get_config().rate_limit_auth_per_min)
    if body.password != body.confirm_password:
        raise HTTPException(422, "Passwords do not match")
    probs = password_problems(body.password, body.email)
    if probs:
        raise HTTPException(422, "Password needs: " + ", ".join(probs))
    user = {"_id": new_id(), "name": body.name.strip(), "email": body.email.lower(), "password_hash": hash_password(body.password),
            "organization": body.organization, "role": body.role, "tokenVersion": 0, "settings": {}, "createdAt": now()}
    try:
        await get_db().users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(409, "An account with this email already exists")
    _set_cookies(response, user, False)
    return _public(user)


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    limiter.check("auth:" + client_ip(request), get_config().rate_limit_auth_per_min)
    limiter.check("login:" + body.email.lower(), 8, 300)
    user = await get_db().users.find_one({"email": body.email.lower()})
    ok = verify_password(body.password, user["password_hash"] if user else None)
    if not user or not ok:
        raise HTTPException(401, "Invalid email or password")
    _set_cookies(response, user, body.remember)
    return _public(user)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/"); response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
async def me(response: Response, user: dict = Depends(current_user)):
    return _public(user)


@router.post("/forgot-password")
async def forgot(body: ForgotIn, request: Request):
    limiter.check("forgot:" + client_ip(request), 5)
    db = get_db(); c = get_config()
    user = await db.users.find_one({"email": body.email.lower()})
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_resets.insert_one({"_id": hash_token(token), "userId": user["_id"], "expiresAt": now() + timedelta(minutes=30)})
        link = f"{c.frontend_url}/reset-password?token={token}"
        if c.dev_print_reset_links and c.env != "production":
            print(f"[DEV] password reset link for {user['email']}: {link}")      # no SMTP configured: dev console only
        # production: send `link` through your email provider here.
    return {"ok": True, "message": "If that email exists, a reset link has been sent."}      # never reveal whether it exists


@router.post("/reset-password")
async def reset(body: ResetIn):
    db = get_db()
    rec = await db.password_resets.find_one_and_delete({"_id": hash_token(body.token)})
    if not rec or rec["expiresAt"].replace(tzinfo=rec["expiresAt"].tzinfo or __import__("datetime").timezone.utc) < now():
        raise HTTPException(400, "Reset link is invalid or has expired")
    user = await db.users.find_one({"_id": rec["userId"]})
    probs = password_problems(body.password, user["email"])
    if probs:
        raise HTTPException(422, "Password needs: " + ", ".join(probs))
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.password)}, "$inc": {"tokenVersion": 1}})
    return {"ok": True}


@router.delete("/me")
async def delete_account(body: DeleteAccountIn, response: Response, user: dict = Depends(current_user)):
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(403, "Password incorrect")
    await delete_user_everything(user["_id"])
    response.delete_cookie(SESSION_COOKIE, path="/"); response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}
