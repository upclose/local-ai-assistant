"""
/api/sessions — manage chat sessions and history.
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import Session, Message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[Session])
async def list_sessions(request: Request):
    return await request.app.state.db.list_sessions()


@router.get("/{session_id}/messages", response_model=list[Message])
async def get_messages(session_id: str, request: Request):
    return await request.app.state.db.get_all_messages(session_id)


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str, request: Request):
    await request.app.state.db.delete_session_messages(session_id)


@router.get("/health/ollama")
async def ollama_health(request: Request):
    available = await request.app.state.ollama.is_available()
    models    = []
    if available:
        try:
            models = await request.app.state.ollama.list_models()
        except Exception:
            pass
    return {"ollama_available": available, "models": models}
