"""
LangGraph state definition for the Orchestrator graph.
"""

from typing import Annotated
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """
    Extends MessagesState (which carries `messages`) with:
      - repo_path: the absolute/relative path to the repository being queried
      - token_count: estimated token count of the current message history,
                     updated by the context monitor after each turn
    """
    repo_path: str
    token_count: int
