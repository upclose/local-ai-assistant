"""
Memory tool — lets the assistant query the FAISS long-term memory store.
"""
import logging
from typing import Optional

from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


def search_memory(query: str, memory: Optional[MemoryService], top_k: int = 5) -> str:
    """
    Search long-term memory for facts relevant to `query`.
    Returns a formatted string for inclusion in the assistant reply.
    """
    if memory is None:
        return "[search_memory] Memory service is not available."

    results = memory.search(query, top_k=top_k)
    if not results:
        return "[search_memory] No relevant facts found."

    lines = [f"Memory search results for '{query}':"]
    for i, r in enumerate(results, 1):
        lines.append(f"  {i}. {r['key']}: {r['value']}  (score={r['score']:.3f})")
    return "\n".join(lines)
