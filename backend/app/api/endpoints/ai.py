from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models import AIMessage, AIConversation
from app.repositories.dataset_repo import get_dataset_for_user, load_dataset_df
from app.schemas import AIAsk
from app.services import ai as ai_service

logger = logging.getLogger("nexus")

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/conversations")
def conversations(user=Depends(get_current_user), db: Session = Depends(get_db)):
    convs = db.query(AIConversation).filter(
        (AIConversation.user_id == user.id) | (AIConversation.user_id.is_(None))
    ).order_by(AIConversation.updated_at.desc()).limit(100).all()
    return {"conversations": [_c(c) for c in convs]}


@router.post("/conversations")
def create_conversation(user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = AIConversation(user_id=user.id, title="New Analysis")
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"conversation": _c(c)}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(AIConversation).filter(AIConversation.id == conversation_id).first()
    if not c:
        raise NotFoundError("Conversation not found.")
    msgs = db.query(AIMessage).filter(AIMessage.conversation_id == conversation_id).order_by(AIMessage.created_at).all()
    return {"conversation": _c(c), "messages": [
        {"id": m.id, "role": m.role, "content": m.content, "artifacts": m.artifacts,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in msgs
    ]}


@router.post("/conversations/{conversation_id}/rename")
def rename_conversation(conversation_id: str, body: dict,
                        user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(AIConversation).filter(AIConversation.id == conversation_id).first()
    if not c:
        raise NotFoundError("Conversation not found.")
    c.title = body.get("title", c.title)[:200]
    db.commit()
    db.refresh(c)
    return {"conversation": _c(c)}


@router.post("/ask")
def ask(payload: AIAsk, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ds = get_dataset_for_user(db, payload.dataset_id, user.id)
    df = load_dataset_df(ds)

    conversation = None
    if payload.conversation_id:
        conversation = db.query(AIConversation).filter(AIConversation.id == payload.conversation_id).first()
    if conversation is None:
        conversation = AIConversation(user_id=user.id, title=payload.message[:60])
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    db.add(AIMessage(conversation_id=conversation.id, role="user", content=payload.message))
    db.commit()

    result = ai_service.answer(df, payload.message)

    artifacts = []
    for spec in result.get("charts", [])[:4]:
        try:
            from app.services import charts as chart_service
            data, error = chart_service.build_chart_data(df, spec["chart_type"], spec)
            artifacts.append({"type": "chart", "chart_type": spec["chart_type"],
                              "config": spec, "data": data, "error": error})
        except Exception as e:
            logger.debug("Failed to build chart artifact: %s", e)
            continue

    message = AIMessage(conversation_id=conversation.id, role="assistant",
                        content=result.get("answer_md", ""), artifacts=artifacts)
    db.add(message)
    db.commit()
    db.refresh(message)

    return {
        "message": {"id": message.id, "role": "assistant", "content": message.content, "artifacts": artifacts},
        "conversation": _c(conversation),
    }


def _c(c: AIConversation) -> dict:
    return {
        "id": c.id, "title": c.title,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }