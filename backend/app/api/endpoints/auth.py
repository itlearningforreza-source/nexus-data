from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_user
from app.core.database import get_db
from app.core.errors import AppError, ConflictError, ValidationError
from app.core.logging import new_request_id
from app.core.security import (
    audit_log_entry,
    create_access_token,
    hash_password,
    verify_password,
)
from app.core.database import db_session
from app.models import AuditLog, User
from app.schemas import AuthLogin, AuthRegister

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(payload: AuthRegister, request: Request, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise ConflictError("An account with this email already exists.")
    user = User(
        email=payload.email.lower(),
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    org = None
    token = create_access_token(user.id)
    db.add(AuditLog(**audit_log_entry(user.id, None, "auth.register", "user", user.id, {"email": user.email})))
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(user)}


@router.post("/login")
def login(payload: AuthLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise ValidationError("Incorrect email or password.")
    if not user.is_active:
        raise ValidationError("This account has been deactivated.")
    from datetime import datetime as _dt
    user.last_login = _dt.utcnow()
    db.add(AuditLog(**audit_log_entry(user.id, None, "auth.login", "user", user.id)))
    db.commit()
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": _user_dict(user)}


def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "avatar_color": u.avatar_color,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }