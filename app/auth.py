"""JWT auth stored in an httpOnly cookie, with role checks."""
import datetime as dt

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response

from .config import JWT_HOURS, JWT_SECRET

COOKIE = "pravi_token"
ROLES = {"engineer", "ee", "auditor"}


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(user) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "name": user.full_name,
        "role": user.role,
        "district": user.district,
        "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=JWT_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def set_auth_cookie(response: Response, request: Request, token: str) -> None:
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        COOKIE, token, httponly=True, secure=secure, samesite="lax",
        max_age=JWT_HOURS * 3600, path="/",
    )


def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Not logged in")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired, please log in again")


def require_role(*roles):
    def check(user: dict = Depends(current_user)) -> dict:
        if roles and user.get("role") not in roles:
            raise HTTPException(403, "Your role cannot do this")
        return user
    return check


STAFF = require_role("engineer", "ee", "auditor")
FIELD = require_role("engineer", "ee")
EE = require_role("ee")
