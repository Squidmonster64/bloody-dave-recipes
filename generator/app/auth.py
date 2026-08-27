"""Password cookie auth with CSRF for Recipe Studio mutations."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import settings

COOKIE_NAME = "bd_studio_session"
CSRF_COOKIE = "bd_studio_csrf"
SESSION_MAX_AGE = 60 * 60 * 12


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="bd-recipe-studio")


def password_configured() -> bool:
    return bool(settings.admin_password_hash or settings.admin_password)


def verify_password(password: str) -> bool:
    if settings.admin_password_hash:
        # Accept sha256:<hex> or raw bcrypt-style hashes via hmac compare of sha256 digest.
        expected = settings.admin_password_hash
        if expected.startswith("sha256:"):
            digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
            return hmac.compare_digest(f"sha256:{digest}", expected)
        # Fallback: direct string compare of precomputed hash value after sha256.
        digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(expected, digest) or hmac.compare_digest(expected, f"sha256:{digest}")
    if settings.admin_password:
        return hmac.compare_digest(password, settings.admin_password)
    # Dev convenience only when no password configured and AUTH_MODE allows open local.
    return settings.auth_mode == "open"


def issue_session(response: Response) -> str:
    token = _serializer().dumps({"role": "admin", "iat": int(time.time())})
    csrf = secrets.token_urlsafe(32)
    secure = settings.studio_base_url.startswith("https://")
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    return csrf


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def read_session(request: Request) -> dict | None:
    if settings.auth_mode == "cloudflare_access":
        # Cloudflare Access injects identity headers after edge auth.
        email = request.headers.get("cf-access-authenticated-user-email")
        if email:
            return {"role": "admin", "email": email}
        # Allow health checks without CF on local.
        if settings.studio_base_url.startswith("http://localhost"):
            return {"role": "admin", "email": "local@dev"}
        return None
    if settings.auth_mode == "open":
        return {"role": "admin", "email": "open@dev"}
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        data = _serializer().loads(raw, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None
    if data.get("role") != "admin":
        return None
    return data


def require_auth(request: Request) -> dict:
    session = read_session(request)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return session


def require_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if settings.auth_mode in {"cloudflare_access", "open"}:
        return
    cookie = request.cookies.get(CSRF_COOKIE) or ""
    header = request.headers.get("x-csrf-token") or ""
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


AuthSession = Annotated[dict, Depends(require_auth)]
