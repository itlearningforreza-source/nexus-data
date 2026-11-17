from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AuthError
from app.core.security import decode_token, rate_limit
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not request.headers.get("x-api-key"):  # allow API key mode? Only bearer used.
        pass
    if credentials is None:
        raise AuthError("Authentication required.")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise AuthError("Invalid or expired token.")
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise AuthError("Invalid token subject.") from None
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise AuthError("Account is inactive or not found.")
    return user


def rate_limited(key_prefix: str):
    def dep(request: Request, user=Depends(get_current_user)):
        key = f"{key_prefix}:{getattr(user, 'id', 'anon')}:{request.client.host if request.client else 'local'}"
        if not rate_limit(key):
            from app.core.errors import RateLimitError
            raise RateLimitError("Too many requests. Please slow down.")
        return user
    return dep


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    return db.query(User).filter(User.id == user_id).first()