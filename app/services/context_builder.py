"""
Context builder — assembles the message list sent to the LLM.

Layers (in order of inclusion):
  1. System prompt  (personality + instructions)
  2. Long-term memory facts  (from FAISS, relevant to current query)
  3. Recent chat history  (last N messages from SQLite)
  4. Current user message
"""
import logging
from typing import Optional

from app.db.database import Database
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful, concise, and honest local AI assistant.
You have access to a set of tools. When you need to use a tool, respond with
EXACTLY this JSON block (no surrounding text before it):

<tool_call>
{{"name": "<tool_name>", "arguments": {{<key>: <value>}}}}
</tool_call>

Available tools:
- read_file(path: str)          – read a local file
- write_note(text: str, filename: str)  – save a note to disk
- search_memory(query: str)     – search long-term memory facts

If no tool is needed, reply normally in plain text.
Never make up information you don't have. Be concise."""


class ContextBuilder:
    def __init__(
        self,
        db: Database,
        memory: Optional[MemoryService],
        max_history: int = 10,
        max_memory_facts: int = 4,
    ):
        self.db = db
        self.memory = memory
        self.max_history = max_history
        self.max_memory_facts = max_memory_facts

    async def build(
        self,
        session_id: str,
        user_message: str,
    ) -> list[dict]:
        """
        Returns a list of {"role": ..., "content": ...} dicts.
        """
        messages: list[dict] = []

        # 1. System prompt
        system_content = SYSTEM_PROMPT

        # 2. Inject relevant long-term facts into system prompt
        if self.memory:
            facts = self.memory.search(user_message, top_k=self.max_memory_facts)
            if facts:
                facts_block = "\n".join(f"- {f['key']}: {f['value']}" for f in facts)
                system_content += f"\n\nRelevant facts about the user:\n{facts_block}"
                logger.debug("Injected %d memory facts into context", len(facts))

        messages.append({"role": "system", "content": system_content})

        # 3. Recent chat history
        history = await self.db.get_recent_messages(session_id, limit=self.max_history)
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # 4. Current user message
        messages.append({"role": "user", "content": user_message})

        logger.debug(
            "Built context: 1 system + %d history + 1 user = %d messages total",
            len(history),
            len(messages),
        )
        return messages
