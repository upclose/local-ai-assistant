"""
Tool executor — parses <tool_call> blocks from LLM output and runs them.

The LLM is instructed (via system prompt) to emit:
    <tool_call>
    {"name": "...", "arguments": {...}}
    </tool_call>

This service detects those blocks, executes the appropriate tool,
then sends a follow-up request to the LLM with the tool result injected.
"""
import json
import logging
import re
from typing import Optional

from app.models.schemas import ToolCall, ToolResult
from app.services.memory_service import MemoryService
from app.tools.file_tools import read_file
from app.tools.note_tools import write_note
from app.tools.memory_tools import search_memory

logger = logging.getLogger(__name__)

_TOOL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)

# Maximum tool-call iterations per turn (prevents infinite loops)
MAX_TOOL_ITERATIONS = 3


class ToolExecutor:
    def __init__(self, notes_dir: str, memory: Optional[MemoryService]):
        self.notes_dir = notes_dir
        self.memory = memory

    # ── Public ────────────────────────────────────────────────────────────────

    def has_tool_call(self, text: str) -> bool:
        return bool(_TOOL_RE.search(text))

    def parse_tool_call(self, text: str) -> Optional[ToolCall]:
        """Extract the first tool call from LLM output."""
        match = _TOOL_RE.search(text)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
            return ToolCall(name=data["name"], arguments=data.get("arguments", {}))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse tool call JSON: %s  — %s", match.group(1), e)
            return None

    def execute(self, call: ToolCall) -> ToolResult:
        """Dispatch to the correct tool function."""
        name = call.name
        args = call.arguments

        try:
            if name == "read_file":
                output = read_file(path=args.get("path", ""))
            elif name == "write_note":
                output = write_note(
                    text=args.get("text", ""),
                    filename=args.get("filename", "untitled"),
                    notes_dir=self.notes_dir,
                )
            elif name == "search_memory":
                output = search_memory(
                    query=args.get("query", ""),
                    memory=self.memory,
                )
            else:
                output = f"[tool_executor] Unknown tool: '{name}'"
            return ToolResult(tool=name, success=True, output=output)
        except Exception as e:
            logger.exception("Tool '%s' raised an exception", name)
            return ToolResult(tool=name, success=False, output=str(e))

    def strip_tool_call(self, text: str) -> str:
        """Remove the <tool_call> block from LLM output."""
        return _TOOL_RE.sub("", text).strip()
