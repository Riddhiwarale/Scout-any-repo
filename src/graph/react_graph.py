"""
Main LangGraph ReAct graph — assembles the Orchestrator, ToolNode,
ContextMonitor, and Compactor into a compiled graph.

Graph topology
--------------

    START
      │
      ▼
  [orchestrator]  ◄──────────────────────┐
      │                                  │
      │ tool_calls present?              │
      ├── Yes ──► [tools] ───────────────┘
      │
      └── No (final answer)
              │
              ▼
          [monitor]
              │
              ├── token_count < 70% ──► END
              │
              └── token_count ≥ 70% ──► [compactor] ──► END
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from src.graph.nodes import (
    compactor_node,
    context_monitor_node,
    make_orchestrator_node,
    make_tool_node,
    route_monitor,
    route_orchestrator,
)
from src.graph.state import AgentState


def build_graph(repo_path: str):
    """
    Build and compile a LangGraph ReAct graph for the given repository path.

    Returns a compiled graph that can be invoked with:
        graph.invoke({"messages": [...], "repo_path": repo_path, "token_count": 0})

    Or streamed with:
        graph.stream(...)
    """
    # --- Nodes ------------------------------------------------------------
    orchestrator_node = make_orchestrator_node(repo_path)
    tool_node = make_tool_node(repo_path)

    # --- Graph construction -----------------------------------------------
    builder = StateGraph(AgentState)

    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("tools", tool_node)
    builder.add_node("monitor", context_monitor_node)
    builder.add_node("compactor", compactor_node)

    # --- Edges ------------------------------------------------------------
    builder.add_edge(START, "orchestrator")

    # After orchestrator: go to tools or to monitor
    builder.add_conditional_edges(
        "orchestrator",
        route_orchestrator,
        {
            "tools": "tools",
            "monitor": "monitor",
        },
    )

    # After tools: back to orchestrator (ReAct loop)
    builder.add_edge("tools", "orchestrator")

    # After monitor: END or compact
    builder.add_conditional_edges(
        "monitor",
        route_monitor,
        {
            "compact": "compactor",
            "__end__": END,
        },
    )

    # After compactor: END
    builder.add_edge("compactor", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Convenience: single-turn invocation
# ---------------------------------------------------------------------------


def ask(
    question: str,
    repo_path: str,
    history: list | None = None,
) -> tuple[str, list]:
    """
    Ask a single question and return (answer_text, updated_history).

    Args:
        question: The user's natural-language question.
        repo_path: Absolute or relative path to the repository.
        history: Optional prior message list (for multi-turn conversations).

    Returns:
        A tuple of (answer_string, new_history_list).
    """
    graph = build_graph(repo_path)

    messages = list(history or [])
    messages.append(HumanMessage(content=question))

    result = graph.invoke(
        {
            "messages": messages,
            "repo_path": repo_path,
            "token_count": 0,
        }
    )

    updated_messages = result["messages"]
    # The last AI message is the final answer
    answer = ""
    for msg in reversed(updated_messages):
        from langchain_core.messages import AIMessage

        if isinstance(msg, AIMessage) and not msg.tool_calls:
            answer = msg.content
            break

    return answer, updated_messages
