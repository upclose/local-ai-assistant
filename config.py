"""
Application settings — loaded from environment / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3")

    # Database
    db_path: str = Field(default="./data/assistant.db")

    # Notes
    notes_dir: str = Field(default="./data/notes")

    # Context window
    max_context_messages: int = Field(default=10)

    # FAISS memory
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    faiss_index_path: str = Field(default="./data/faiss_index")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    log_level: str = Field(default="info")


# Singleton — import this everywhere
settings = Settings()
