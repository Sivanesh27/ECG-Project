from fastapi import Depends, HTTPException, Request
from .db import get_db
from .security import SESSION_COOKIE, decode_token, check_csrf


async def current_user(request: Request) -> dict:
    """Identity is derived ONLY from the signed httpOnly cookie. Request bodies/params never supply a user id."""
    tok = request.cookies.get(SESSION_COOKIE)
    payload = decode_token(tok) if tok else None
    if not payload:
        raise HTTPException(401, "Not authenticated")
    user = await get_db().users.find_one({"_id": payload["sub"]})
    if not user or user.get("tokenVersion", 0) != payload.get("ver", 0):
        raise HTTPException(401, "Session expired")
    check_csrf(request)
    return user
