"""
cli.py — Terminal interface for the Local AI Assistant.

Usage:
    python cli.py chat                        # start a chat session
    python cli.py chat --session my-project   # named session
    python cli.py sessions                    # list past sessions
    python cli.py memory list                 # show stored facts
    python cli.py memory add <key> <value>    # add a fact manually
    python cli.py memory delete <key>         # delete a fact
    python cli.py models                      # list Ollama models
"""
import asyncio
import json
import sys
from datetime import datetime
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import print as rprint

# ── App & helpers ─────────────────────────────────────────────────────────────

app     = typer.Typer(help="Local AI Assistant — offline, no paid APIs.")
console = Console()

# Default API base — override with env var LOCAL_AI_URL
import os
BASE_URL = os.getenv("LOCAL_AI_URL", "http://localhost:8000")


def _api(path: str) -> str:
    return f"{BASE_URL}{path}"


def _check_server() -> bool:
    try:
        r = httpx.get(_api("/api/sessions/health/ollama"), timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# ── chat ──────────────────────────────────────────────────────────────────────

@app.command()
def chat(
    session: str = typer.Option("default", "--session", "-s", help="Session ID"),
    model:   str = typer.Option(None,      "--model",   "-m", help="Override LLM model"),
    stream:  bool = typer.Option(True,     "--stream/--no-stream",   help="Streaming mode"),
):
    """Start an interactive chat session."""
    if not _check_server():
        console.print(
            "[bold red]✗ Cannot reach the API server.[/] "
            f"Make sure it's running:  uvicorn main:app --reload  (at {BASE_URL})"
        )
        raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold green]Local AI Assistant[/]\n"
            f"session=[cyan]{session}[/]   model=[cyan]{model or 'default'}[/]\n"
            f"Type [bold]/quit[/] to exit · [bold]/clear[/] to wipe session · "
            f"[bold]/memory[/] to list facts",
            expand=False,
        )
    )

    asyncio.run(_chat_loop(session, model, stream))


async def _chat_loop(session_id: str, model: Optional[str], stream: bool):
    async with httpx.AsyncClient(timeout=120) as client:
        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]You[/]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Bye![/]")
                break

            if not user_input:
                continue

            # ── slash commands ────────────────────────────────────────────────
            if user_input.lower() in ("/quit", "/exit", "/q"):
                console.print("[dim]Bye![/]")
                break

            if user_input.lower() == "/clear":
                await client.delete(_api(f"/api/sessions/{session_id}"))
                console.print("[yellow]Session cleared.[/]")
                continue

            if user_input.lower() == "/memory":
                r = await client.get(_api("/api/memory"))
                facts = r.json()
                if facts:
                    t = Table("Key", "Value", "Source", title="Long-term memory")
                    for f in facts:
                        t.add_row(f["key"], f["value"], f.get("source", ""))
                    console.print(t)
                else:
                    console.print("[dim]No facts stored yet.[/]")
                continue

            if user_input.lower() == "/sessions":
                r = await client.get(_api("/api/sessions"))
                sessions = r.json()
                t = Table("ID", "Title", "Messages", title="Sessions")
                for s in sessions:
                    t.add_row(s["id"], s.get("title") or "", str(s.get("message_count", 0)))
                console.print(t)
                continue

            # ── regular message ───────────────────────────────────────────────
            payload = {"message": user_input, "session_id": session_id, "stream": False}
            if model:
                payload["model"] = model

            console.print("\n[bold magenta]Assistant[/]", end=" ")

            if stream:
                await _stream_response(client, session_id, user_input, model)
            else:
                await _full_response(client, payload)


async def _full_response(client: httpx.AsyncClient, payload: dict):
    """Send request and print the full reply at once."""
    try:
        r = await client.post(_api("/api/chat"), json=payload)
        r.raise_for_status()
        data = r.json()
        reply = data["reply"]
        if data.get("tools_used"):
            console.print(f"[dim](tools: {', '.join(data['tools_used'])})[/]")
        console.print(Markdown(reply))
    except httpx.HTTPStatusError as e:
        console.print(f"[red]API error {e.response.status_code}:[/] {e.response.text}")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")


async def _stream_response(
    client: httpx.AsyncClient,
    session_id: str,
    message: str,
    model: Optional[str],
):
    """Stream tokens and print them as they arrive."""
    payload: dict = {"message": message, "session_id": session_id, "stream": True}
    if model:
        payload["model"] = model

    buffer: list[str] = []
    try:
        async with client.stream("POST", _api("/api/chat/stream"), json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                token = line[6:]  # strip "data: "
                if token == "[DONE]":
                    break
                if token.startswith("[ERROR]"):
                    console.print(f"\n[red]{token}[/]")
                    break
                buffer.append(token)
                console.print(token, end="", highlight=False)
        console.print()  # newline after streamed reply
    except Exception as e:
        console.print(f"\n[red]Stream error:[/] {e}")


# ── sessions ──────────────────────────────────────────────────────────────────

@app.command()
def sessions():
    """List all chat sessions."""
    try:
        r = httpx.get(_api("/api/sessions"), timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    if not data:
        console.print("[dim]No sessions yet.[/]")
        return

    t = Table("Session ID", "Title", "Messages", "Created", title="Chat Sessions")
    for s in data:
        t.add_row(
            s["id"],
            s.get("title") or "[dim]—[/]",
            str(s.get("message_count", 0)),
            s.get("created_at", "")[:16],
        )
    console.print(t)


# ── memory ────────────────────────────────────────────────────────────────────

memory_app = typer.Typer(help="Manage long-term memory facts.")
app.add_typer(memory_app, name="memory")


@memory_app.command("list")
def memory_list():
    """List all stored memory facts."""
    try:
        r = httpx.get(_api("/api/memory"), timeout=10)
        r.raise_for_status()
        facts = r.json()
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    if not facts:
        console.print("[dim]No facts stored.[/]")
        return

    t = Table("Key", "Value", "Source", "Updated", title="Memory Facts")
    for f in facts:
        t.add_row(f["key"], f["value"], f.get("source", ""), (f.get("created_at") or "")[:16])
    console.print(t)


@memory_app.command("add")
def memory_add(
    key:   str = typer.Argument(..., help="Fact key, e.g. 'user_name'"),
    value: str = typer.Argument(..., help="Fact value"),
):
    """Add or update a memory fact."""
    payload = {"key": key, "value": value, "source": "manual"}
    try:
        r = httpx.post(_api("/api/memory"), json=payload, timeout=10)
        r.raise_for_status()
        console.print(f"[green]✓[/] Saved fact: [bold]{key}[/] = {value}")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)


@memory_app.command("delete")
def memory_delete(key: str = typer.Argument(..., help="Key to delete")):
    """Delete a memory fact by key."""
    try:
        r = httpx.delete(_api(f"/api/memory/{key}"), timeout=10)
        if r.status_code == 204:
            console.print(f"[green]✓[/] Deleted fact: [bold]{key}[/]")
        elif r.status_code == 404:
            console.print(f"[yellow]Fact '{key}' not found.[/]")
        else:
            r.raise_for_status()
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)


# ── models ────────────────────────────────────────────────────────────────────

@app.command()
def models():
    """List models available in Ollama."""
    try:
        r = httpx.get(_api("/api/sessions/health/ollama"), timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    if not data["ollama_available"]:
        console.print("[red]✗ Ollama is not running.[/]")
        raise typer.Exit(1)

    model_list = data.get("models", [])
    if not model_list:
        console.print("[yellow]Ollama is running but no models are pulled yet.[/]")
        console.print("Run:  [bold]ollama pull llama3[/]")
        return

    t = Table("Model", title="Available Ollama Models")
    for m in model_list:
        t.add_row(m)
    console.print(t)


# ── entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
