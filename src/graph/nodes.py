"""
LangGraph node functions for the Orchestrator graph.

Nodes:
  - orchestrator_node: llama-3.3-70b-versatile ReAct reasoning step
  - tool_node:         Executes tool calls made by the Orchestrator
  - context_monitor_node: Counts tokens; triggers compaction if ≥ 70%
  - compactor_node:    Fast model history compression
"""

from __future__ import annotations

import json
from typing import Any

import tiktoken
from langchain_groq import ChatGroq
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.prebuilt import ToolNode

from src.agents.explore_agent import make_explore_tool
from src.config import settings
from src.graph.prompts import COMPACTOR_SYSTEM_PROMPT, ORCHESTRATOR_SYSTEM_PROMPT
from src.graph.state import AgentState
from src.tools import create_tools

# ---------------------------------------------------------------------------
# Token counting (approximation via tiktoken cl100k_base)
# ---------------------------------------------------------------------------
_ENCODER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(messages: list) -> int:
    """Rough token count across all messages."""
    total = 0
    for msg in messages:
        content = msg.content if hasattr(msg, "content") else str(msg)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += len(_ENCODER.encode(block.get("text", "")))
                else:
                    total += len(_ENCODER.encode(str(block)))
        else:
            total += len(_ENCODER.encode(str(content)))
    return total


# ---------------------------------------------------------------------------
# Factory: build LLMs & tool lists
# ---------------------------------------------------------------------------


def _build_orchestrator_llm(repo_path: str):
    """Create the orchestrator LLM with all tools (including explore_agent) bound."""
    core_tools = create_tools(repo_path)
    explore_tool = make_explore_tool(repo_path)
    all_tools = core_tools + [explore_tool]

    llm = ChatGroq(
        model=settings.orchestrator_model,
        temperature=0,
        api_key=settings.groq_api_key,
        max_tokens=8192,
    )
    return llm.bind_tools(all_tools), all_tools


def _build_tool_node(repo_path: str) -> tuple[ToolNode, dict[str, Any]]:
    """Build a LangGraph ToolNode with all tools for the given repo."""
    core_tools = create_tools(repo_path)
    explore_tool = make_explore_tool(repo_path)
    all_tools = core_tools + [explore_tool]
    tool_map = {t.name: t for t in all_tools}
    return ToolNode(all_tools), tool_map


# ---------------------------------------------------------------------------
# Node: Orchestrator
# ---------------------------------------------------------------------------


def make_orchestrator_node(repo_path: str):
    """Return an orchestrator node function bound to `repo_path`."""
    llm_with_tools, _ = _build_orchestrator_llm(repo_path)
    system_message = SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT)

    def orchestrator_node(state: AgentState) -> dict:
        messages = state["messages"]
        full_messages = [system_message] + list(messages)
        response: AIMessage = llm_with_tools.invoke(full_messages)
        return {"messages": [response]}

    return orchestrator_node


# ---------------------------------------------------------------------------
# Node: Tool execution
# ---------------------------------------------------------------------------


def make_tool_node(repo_path: str) -> ToolNode:
    """Return a LangGraph ToolNode with all tools bound to `repo_path`."""
    node, _ = _build_tool_node(repo_path)
    return node


# ---------------------------------------------------------------------------
# Node: Context Monitor
# ---------------------------------------------------------------------------


def context_monitor_node(state: AgentState) -> dict:
    """
    Count the current token usage and store it in state.
    The router uses this count to decide whether to trigger the Compactor.
    """
    messages = state["messages"]
    count = _count_tokens(messages)
    return {"token_count": count}


# ---------------------------------------------------------------------------
# Node: Compactor
# ---------------------------------------------------------------------------


def compactor_node(state: AgentState) -> dict:
    """
    Compress the conversation history when the context threshold is exceeded.
    Replaces the raw message list with a single structured summary message,
    followed by the most recent human message (for continuity).
    """
    messages = state["messages"]

    llm = ChatGroq(
        model=settings.compactor_model,
        temperature=0,
        api_key=settings.groq_api_key,
        max_tokens=4096,
    )

    history_text = _serialize_messages(messages)
    compaction_prompt = (
        f"Here is the full conversation history to compress:\n\n{history_text}"
    )

    summary_response: AIMessage = llm.invoke(
        [
            SystemMessage(content=COMPACTOR_SYSTEM_PROMPT),
            HumanMessage(content=compaction_prompt),
        ]
    )

    summary_content = summary_response.content

    last_human = _find_last_human_message(messages)
    compressed: list = [SystemMessage(content=summary_content)]
    if last_human:
        compressed.append(last_human)

    return {"messages": compressed, "token_count": _count_tokens(compressed)}


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------


def route_orchestrator(state: AgentState) -> str:
    """
    After the orchestrator runs:
      - If the last message has tool_calls → route to 'tools'
      - Otherwise (final answer) → route to 'monitor'
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "monitor"


def route_monitor(state: AgentState) -> str:
    """
    After the context monitor runs:
      - If token_count ≥ threshold → route to 'compactor'
      - Otherwise → END
    """
    token_count = state.get("token_count", 0)
    threshold_tokens = int(
        settings.orchestrator_context_window * settings.context_threshold
    )
    if token_count >= threshold_tokens:
        return "compact"
    return "__end__"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _serialize_messages(messages: list) -> str:
    """Convert message list to a readable text representation."""
    parts: list[str] = []
    for msg in messages:
        role = type(msg).__name__.replace("Message", "")
        content = msg.content
        if isinstance(content, list):
            text_parts = [
                b.get("text", str(b)) if isinstance(b, dict) else str(b)
                for b in content
            ]
            content = "\n".join(text_parts)
        if isinstance(msg, AIMessage) and msg.tool_calls:
            calls = json.dumps(msg.tool_calls, default=str, indent=2)
            content = f"{content}\n[Tool calls: {calls}]" if content else f"[Tool calls: {calls}]"
        parts.append(f"[{role}]\n{content}")
    return "\n\n---\n\n".join(parts)


def _find_last_human_message(messages: list):
    """Return the most recent HumanMessage, or None."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg
    return None
