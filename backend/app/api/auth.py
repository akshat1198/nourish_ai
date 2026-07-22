"""Auth dependency.

`AUTH_MODE=disabled` (default): identity comes from an `X-User-Key` header,
falling back to `"dev-user"`. Keeps the whole test suite + curl workflow open,
no tokens required.

`AUTH_MODE=jwt`: verify an HS256 bearer minted by the Next.js Auth.js layer with
`AUTH_SHARED_SECRET`; identity = `f"google:{sub}"`. `X-User-Key` is IGNORED in
jwt mode so it can never be a spoofing vector.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from app.core.config import settings


def get_current_user_key(request: Request) -> str:
    if settings.AUTH_MODE != "jwt":
        return request.headers.get("X-User-Key") or "dev-user"

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = auth[len("Bearer "):]
    try:
        import jwt  # PyJWT; lazy import so disabled mode needs no dependency

        payload = jwt.decode(
            token,
            settings.AUTH_SHARED_SECRET,
            algorithms=["HS256"],
            audience=settings.AUTH_JWT_AUD,
            issuer=settings.AUTH_JWT_ISS,
        )
    except Exception as e:  # PyJWT raises many subclasses; normalize to 401
        raise HTTPException(401, f"invalid token: {e}")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(401, "token missing sub")
    return f"google:{sub}"


def require_admin(request: Request) -> None:
    """Gate for the admin observability endpoints. Fail-closed: an unset
    ADMIN_TOKEN locks the route regardless of what header a caller sends."""
    token = settings.ADMIN_TOKEN
    if not token or request.headers.get("X-Admin-Token") != token:
        raise HTTPException(403, "admin access required")
