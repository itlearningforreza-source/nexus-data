from __future__ import annotations

import hashlib
import secrets
import time
import hmac
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from app.core.config import settings

_local = threading.local()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 210_000
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return f"pbkdf2${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, _iter, salt_hex, hash_hex = stored.split("$")
        iterations = int(_iter)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None


def make_secret_id() -> str:
    return secrets.token_urlsafe(10)


_THROTTLE: dict[str, list[float]] = {}
_THROTTLE_LOCK = threading.Lock()


def rate_limit(key: str, max_requests: int | None = None, window: int | None = None) -> bool:
    """Return True if allowed, False if over limit."""
    if not settings.RATE_LIMIT_ENABLED:
        return True
    limit = max_requests or settings.RATE_LIMIT_MAX
    window_s = window or settings.RATE_LIMIT_WINDOW_SECONDS
    now = time.monotonic()
    with _THROTTLE_LOCK:
        bucket = _THROTTLE.setdefault(key, [])
        bucket[:] = [t for t in bucket if now - t < window_s]
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


def audit_log_entry(user_id: int | None, org_id: int | None, action: str,
                    resource: str, resource_id: str | int | None = None,
                    detail: dict[str, Any] | None = None) -> dict[str, Any]:
    from datetime import datetime
    return {
        "user_id": user_id,
        "organization_id": org_id,
        "action": action,
        "resource": resource,
        "resource_id": str(resource_id) if resource_id is not None else None,
        "detail": detail or {},
        "created_at": datetime.utcnow(),
    }