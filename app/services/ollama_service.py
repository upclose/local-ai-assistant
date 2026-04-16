"""
Ollama service — wraps the Ollama REST API.
Supports both full-response and streaming modes.
"""
import json
import logging
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

OLLAMA_CHAT_URL = "{base}/api/chat"
OLLAMA_TAGS_URL = "{base}/api/tags"
OLLAMA_SHOW_URL = "{base}/api/show"


class OllamaService:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    # ── Health ────────────────────────────────────────────────────────────────

    async def is_available(self) -> bool:
        """Return True if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(OLLAMA_TAGS_URL.format(base=self.base_url))
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """Return names of locally available models."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(OLLAMA_TAGS_URL.format(base=self.base_url))
            r.raise_for_status()
            data = r.json()
            return [m["name"] for m in data.get("models", [])]

    # ── Chat ──────────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> str:
        """
        Send messages to Ollama and return the full reply as a string.
        `messages` must follow OpenAI-style format:
            [{"role": "user" | "assistant" | "system", "content": "..."}]
        """
        model = model or self.model
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.debug("Sending %d messages to Ollama model %s", len(messages), model)
            r = await client.post(
                OLLAMA_CHAT_URL.format(base=self.base_url),
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return data["message"]["content"]

    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream tokens from Ollama.
        Yields text chunks as they arrive.
        """
        model = model or self.model
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                OLLAMA_CHAT_URL.format(base=self.base_url),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        logger.warning("Could not parse stream chunk: %s", line)
