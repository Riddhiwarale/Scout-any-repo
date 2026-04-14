"""
FastAPI serving layer — exposes the ReAct agent as a REST API with
Server-Sent Events (SSE) streaming support.

Endpoints
---------
POST /chat          — non-streaming, returns JSON
POST /chat/stream   — streaming via SSE (token-by-token)
DELETE /session/{id} — clear conversation history for a session
GET  /health        — health check
"""

from __future__ import annotations

import asyncio
import uuid
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.config import settings
from src.graph.react_graph import build_graph

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GitHub Repository Q&A Agent",
    description=(
        "Agentic Q&A over any git repository. "
        "Uses a two-agent ReAct architecture (Sonnet + Haiku) with "
        "6 purpose-built tools."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory session store  {session_id: {"messages": [...], "repo_path": str}}
# ---------------------------------------------------------------------------
_sessions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str = Field(..., description="Natural language question about the repository")
    repo_path: str = Field(
        default=settings.repo_path,
        description="Absolute or relative path to the cloned repository",
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for multi-turn conversations. Omit to start a new session.",
    )


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    token_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_or_create_session(
    session_id: str | None, repo_path: str
) -> tuple[str, list]:
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        return session_id, session["messages"]
    new_id = session_id or str(uuid.uuid4())
    _sessions[new_id] = {"messages": [], "repo_path": repo_path}
    return new_id, []


def _update_session(session_id: str, messages: list, repo_path: str):
    _sessions[session_id] = {"messages": messages, "repo_path": repo_path}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "orchestrator_model": settings.orchestrator_model}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Non-streaming Q&A endpoint. Returns the full answer once the agent
    finishes its ReAct loop.
    """
    session_id, history = _get_or_create_session(req.session_id, req.repo_path)

    graph = build_graph(req.repo_path)
    messages = list(history) + [HumanMessage(content=req.question)]

    try:
        result = await asyncio.to_thread(
            graph.invoke,
            {
                "messages": messages,
                "repo_path": req.repo_path,
                "token_count": 0,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    updated = result["messages"]
    token_count = result.get("token_count", 0)

    # Extract final answer
    answer = ""
    for msg in reversed(updated):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            answer = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    _update_session(session_id, updated, req.repo_path)
    return ChatResponse(answer=answer, session_id=session_id, token_count=token_count)


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming Q&A endpoint using Server-Sent Events.
    Streams the Orchestrator's token output as it is generated.

    Each SSE event has:
      - data: the token or chunk text
      - event: "token" | "done" | "error"
    """
    session_id, history = _get_or_create_session(req.session_id, req.repo_path)

    async def event_generator() -> AsyncGenerator[dict, None]:
        graph = build_graph(req.repo_path)
        messages = list(history) + [HumanMessage(content=req.question)]

        try:
            # LangGraph stream mode: stream individual node outputs
            final_messages = messages
            token_count = 0

            async for chunk in graph.astream(
                {
                    "messages": messages,
                    "repo_path": req.repo_path,
                    "token_count": 0,
                },
                stream_mode="updates",
            ):
                for node_name, node_output in chunk.items():
                    if node_name == "orchestrator":
                        msgs = node_output.get("messages", [])
                        for msg in msgs:
                            if isinstance(msg, AIMessage) and not msg.tool_calls:
                                content = (
                                    msg.content
                                    if isinstance(msg.content, str)
                                    else str(msg.content)
                                )
                                # Stream word by word for a smoother experience
                                for word in content.split(" "):
                                    yield {
                                        "event": "token",
                                        "data": word + " ",
                                    }
                    if node_name == "monitor":
                        token_count = node_output.get("token_count", 0)
                    # Track final message state
                    if "messages" in node_output:
                        final_messages = node_output["messages"]

            _update_session(session_id, final_messages, req.repo_path)
            yield {
                "event": "done",
                "data": f'{{"session_id": "{session_id}", "token_count": {token_count}}}',
            }

        except Exception as exc:
            yield {"event": "error", "data": str(exc)}

    return EventSourceResponse(event_generator())


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear the conversation history for a session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del _sessions[session_id]
    return {"status": "cleared", "session_id": session_id}


@app.get("/sessions")
async def list_sessions():
    """List all active sessions (for debugging)."""
    return {
        sid: {
            "repo_path": data["repo_path"],
            "message_count": len(data["messages"]),
        }
        for sid, data in _sessions.items()
    }
