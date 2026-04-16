"""
main.py — FastAPI application entry point.

Startup sequence:
  1. Initialise SQLite database
  2. Load FAISS memory index (or create fresh one)
  3. Warm up Ollama connection check
  4. Register API routers
  5. Mount static frontend
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from app.api import chat_router, memory_router, sessions_router
from app.db.database import Database
from app.services.ollama_service import OllamaService
from app.services.memory_service import MemoryService
from app.services.context_builder import ContextBuilder
from app.services.tool_executor import ToolExecutor

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise and teardown all services."""
    logger.info("═══ Starting Local AI Assistant ═══")

    # 1. Database
    db = Database(settings.db_path)
    await db.init()

    # 2. Ollama
    ollama = OllamaService(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
    )
    available = await ollama.is_available()
    if available:
        models = await ollama.list_models()
        logger.info("Ollama is UP — available models: %s", models)
    else:
        logger.warning(
            "Ollama is NOT reachable at %s — chat will fail until it starts.",
            settings.ollama_base_url,
        )

    # 3. FAISS memory (optional — gracefully skips if deps missing)
    memory: MemoryService | None = None
    try:
        memory = MemoryService(
            index_dir=settings.faiss_index_path,
            model_name=settings.embedding_model,
        )
        logger.info("Memory service ready (%d stored facts)", memory.count())
    except Exception as e:
        logger.warning("Memory service unavailable: %s", e)

    # 4. Context builder + tool executor
    context_builder = ContextBuilder(
        db=db,
        memory=memory,
        max_history=settings.max_context_messages,
    )
    tool_executor = ToolExecutor(
        notes_dir=settings.notes_dir,
        memory=memory,
    )

    # Attach to app state so routers can access
    app.state.db              = db
    app.state.ollama          = ollama
    app.state.memory          = memory
    app.state.context_builder = context_builder
    app.state.tool_executor   = tool_executor

    logger.info("═══ Ready — listening on http://%s:%d ═══", settings.host, settings.port)
    yield  # ← application runs here

    logger.info("Shutting down…")


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Local AI Assistant",
    description="Offline AI assistant powered by Ollama — no paid APIs.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(sessions_router)

# Serve frontend (index.html at "/")
frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(str(frontend_dir / "index.html"))


# ── Dev entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level,
    )
