from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import User  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    existing = db.query(User).filter(User.email == "demo@nexus.local").first()
    if existing:
        print("Demo user already exists.")
    else:
        user = User(email="demo@nexus.local", name="Demo Analyst",
                    password_hash=hash_password("nexusdemo123"))
        db.add(user)
        db.commit()
        print("Created demo user: demo@nexus.local / nexusdemo123")
    db.close()


if __name__ == "__main__":
    main()