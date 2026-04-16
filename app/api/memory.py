"""
/api/memory — CRUD for long-term memory facts.
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import MemoryFact

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", response_model=list[MemoryFact])
async def list_facts(request: Request):
    """Return all stored memory facts."""
    return await request.app.state.db.get_all_facts()


@router.post("", response_model=MemoryFact, status_code=201)
async def add_fact(request: Request, fact: MemoryFact):
    """Add or update a memory fact."""
    db     = request.app.state.db
    memory = request.app.state.memory

    await db.upsert_fact(fact.key, fact.value, source=fact.source)
    if memory:
        memory.add(fact.key, fact.value)

    stored = await db.get_fact(fact.key)
    return stored


@router.delete("/{key}", status_code=204)
async def delete_fact(key: str, request: Request):
    """Delete a fact by key."""
    deleted = await request.app.state.db.delete_fact(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Fact '{key}' not found")
