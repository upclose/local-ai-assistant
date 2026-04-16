"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: str = Field(default="default")
    model: Optional[str] = Field(default=None)  # override env default
    stream: bool = Field(default=False)


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    model: str
    tools_used: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Memory ────────────────────────────────────────────────────────────────────

class Message(BaseModel):
    id: Optional[int] = None
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: Optional[datetime] = None


class MemoryFact(BaseModel):
    id: Optional[int] = None
    key: str = Field(..., description="Short label, e.g. 'user_name'")
    value: str
    source: str = Field(default="manual")   # 'manual' | 'extracted'
    created_at: Optional[datetime] = None


# ── Tools ─────────────────────────────────────────────────────────────────────

class ToolCall(BaseModel):
    name: str
    arguments: dict


class ToolResult(BaseModel):
    tool: str
    success: bool
    output: str


# ── Sessions ──────────────────────────────────────────────────────────────────

class Session(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    message_count: int = 0
