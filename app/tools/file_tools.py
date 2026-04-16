"""
File-system tools exposed to the assistant.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Guard: only allow reading from safe directories
_SAFE_READ_ROOTS = [Path.cwd(), Path.home() / "Documents"]


def _is_safe_path(path: Path) -> bool:
    resolved = path.resolve()
    return any(
        resolved.is_relative_to(root.resolve()) for root in _SAFE_READ_ROOTS
    )


def read_file(path: str) -> str:
    """
    Read a text file from disk.
    Returns the file contents or an error message.
    """
    p = Path(path)
    if not _is_safe_path(p):
        return f"[read_file] Access denied: '{path}' is outside allowed directories."
    if not p.exists():
        return f"[read_file] File not found: '{path}'"
    if not p.is_file():
        return f"[read_file] Not a file: '{path}'"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        # Limit output to avoid flooding context
        max_chars = 4000
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n... [truncated at {max_chars} chars]"
        logger.info("read_file: %s (%d chars)", path, len(content))
        return content
    except Exception as e:
        return f"[read_file] Error reading '{path}': {e}"
