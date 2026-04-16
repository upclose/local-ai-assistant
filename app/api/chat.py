"""
/api/chat  — core chat endpoint.
Handles tool-call loops: LLM → tool → LLM → final reply.
"""
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, ChatResponse
from app.services.tool_executor import MAX_TOOL_ITERATIONS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    """
    Main chat endpoint.

    Flow:
      1. Build context (system + memory facts + history + user msg)
      2. Call LLM
      3. If response contains a <tool_call>, execute tool and re-query LLM
      4. Save user msg + final assistant reply to DB
      5. Return reply
    """
    state = request.app.state

    db              = state.db
    ollama          = state.ollama
    context_builder = state.context_builder
    tool_executor   = state.tool_executor
    memory          = state.memory

    model = body.model or ollama.model

    # ---------- build initial context ----------
    messages = await context_builder.build(body.session_id, body.message)

    tools_used: list[str] = []

    # ---------- tool-call loop ----------
    for iteration in range(MAX_TOOL_ITERATIONS + 1):
        try:
            raw_reply = await ollama.chat(messages, model=model)
        except Exception as e:
            logger.exception("Ollama call failed")
            raise HTTPException(status_code=502, detail=f"LLM error: {e}")

        if not tool_executor.has_tool_call(raw_reply):
            # No tool needed — we have the final reply
            final_reply = raw_reply.strip()
            break

        if iteration == MAX_TOOL_ITERATIONS:
            # Safety valve: stop looping
            final_reply = tool_executor.strip_tool_call(raw_reply).strip()
            logger.warning("Max tool iterations reached; returning partial reply")
            break

        # Parse and execute tool
        call = tool_executor.parse_tool_call(raw_reply)
        if call is None:
            final_reply = tool_executor.strip_tool_call(raw_reply).strip()
            break

        result = tool_executor.execute(call)
        tools_used.append(call.name)
        logger.info("Tool '%s' executed (success=%s)", call.name, result.success)

        # Inject tool result back into the conversation so the LLM can continue
        messages.append({"role": "assistant", "content": raw_reply})
        messages.append({
            "role": "user",
            "content": (
                f"[Tool result for {call.name}]\n{result.output}\n\n"
                "Now please continue answering the original request using this result."
            ),
        })
    else:
        # Loop exhausted without break (shouldn't happen)
        final_reply = ""

    # ---------- persist to DB ----------
    await db.add_message(body.session_id, "user", body.message)
    await db.add_message(body.session_id, "assistant", final_reply)

    # Auto-generate session title from first user message
    sessions = await db.list_sessions()
    for s in sessions:
        if s.id == body.session_id and s.title is None:
            title = body.message[:60] + ("…" if len(body.message) > 60 else "")
            await db.update_session_title(body.session_id, title)
            break

    return ChatResponse(
        reply=final_reply,
        session_id=body.session_id,
        model=model,
        tools_used=tools_used,
    )


@router.post("/stream")
async def chat_stream(request: Request, body: ChatRequest):
    """
    Streaming variant — returns server-sent events (text/event-stream).
    Tool calls are NOT supported in streaming mode for simplicity.
    """
    state = request.app.state
    db              = state.db
    ollama          = state.ollama
    context_builder = state.context_builder

    model = body.model or ollama.model
    messages = await context_builder.build(body.session_id, body.message)

    await db.add_message(body.session_id, "user", body.message)

    full_reply_parts: list[str] = []

    async def event_generator():
        try:
            async for token in ollama.chat_stream(messages, model=model):
                full_reply_parts.append(token)
                yield f"data: {token}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"
        finally:
            full_reply = "".join(full_reply_parts)
            if full_reply:
                await db.add_message(body.session_id, "assistant", full_reply)
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
