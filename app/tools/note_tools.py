"""
Note-taking tool — saves text snippets to the notes directory.
"""
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def write_note(text: str, filename: str, notes_dir: str = "./data/notes") -> str:
    """
    Write `text` to <notes_dir>/<filename>.
    Sanitises the filename and auto-appends .txt if needed.
    Returns a success or error message.
    """
    # Sanitise filename — strip anything that isn't alphanumeric / dash / underscore / dot
    safe_name = re.sub(r"[^\w\-.]", "_", filename.strip())
    if not safe_name:
        safe_name = f"note_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    if not safe_name.endswith((".txt", ".md")):
        safe_name += ".txt"

    notes_path = Path(notes_dir)
    notes_path.mkdir(parents=True, exist_ok=True)
    target = notes_path / safe_name

    try:
        target.write_text(text, encoding="utf-8")
        logger.info("write_note: saved %s (%d chars)", target, len(text))
        return f"[write_note] Note saved to '{target}'"
    except Exception as e:
        return f"[write_note] Failed to save '{target}': {e}"
