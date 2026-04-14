"""
Explore Agent — a fast Groq-powered ReAct agent that handles deep, multi-step
codebase investigations on behalf of the Orchestrator.

The Orchestrator calls `make_explore_tool(repo_path)` which returns a
LangChain @tool. From the Orchestrator's perspective this is just another
tool; internally it runs its own synchronous ReAct loop.
"""

from __future__ import annotations

from typing import Any

from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from src.config import settings
from src.tools import create_tools

# ---------------------------------------------------------------------------
# System prompt for the Explore Agent
# ---------------------------------------------------------------------------

EXPLORE_SYSTEM_PROMPT = """\
You are the Explore Agent — a specialist in deep, multi-file codebase investigation.

Your job is to autonomously explore the repository and answer the question given to you.
You have access to grep, glob, read, bash (git), and extract_symbols tools.

## Strategy
1. Start with a hypothesis. Grep for the most distinctive terms in the question.
2. Follow the trail. If a grep result references other files, read those too.
3. Trace cross-file references — imports, call sites, data flow.
4. Use extract_symbols to get a table of contents for large files before reading them.
5. Use git log / git blame to understand WHY code exists when that context matters.
6. Continue until you have a complete, confident answer.

## Output format
When you have enough information, respond with a STRUCTURED SUMMARY:

**Files Examined:** (list the key files)
**Key Findings:** (bullet points of the most important discoveries)
**Answer:** (direct answer to the question)

Do not produce partial answers. Explore until you can give a complete, accurate response.
"""

# ---------------------------------------------------------------------------
# Max iterations guard — prevents runaway loops
# ---------------------------------------------------------------------------
_MAX_ITERATIONS = 20


def make_explore_tool(repo_path: str):
    """Return an explore_agent tool bound to `repo_path`."""

    # Fast Groq model for execution-heavy investigation
    explore_llm = ChatGroq(
        model=settings.explore_model,
        temperature=0,
        api_key=settings.groq_api_key,
        max_tokens=8192,
    )

    # Tools available to the Explore Agent (no recursion — exclude explore_agent)
    explore_tools = create_tools(repo_path)
    tool_map: dict[str, Any] = {t.name: t for t in explore_tools}
    llm_with_tools = explore_llm.bind_tools(explore_tools)

    @tool
    def explore_agent(question: str) -> str:
        """
        Delegate a COMPLEX, multi-file codebase investigation to the Explore Agent.
        Use this when answering the question requires:
          - Tracing logic across multiple files
          - Following import chains or call graphs
          - Understanding data flow end-to-end
          - Requiring 5+ tool calls to answer

        The Explore Agent runs autonomously and returns a structured summary.
        Do NOT use this for simple, single-target lookups — call grep/read directly.

        Args:
            question: A detailed, self-contained question for the Explore Agent.
                      Include all relevant context from the conversation so far.
        """
        messages: list = [
            SystemMessage(content=EXPLORE_SYSTEM_PROMPT),
            HumanMessage(content=question),
        ]

        for _ in range(_MAX_ITERATIONS):
            response: AIMessage = llm_with_tools.invoke(messages)
            messages.append(response)

            # No tool calls → agent has finished reasoning
            if not response.tool_calls:
                return response.content or "(Explore Agent returned no content)"

            # Execute each tool call
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_id = tc["id"]

                if tool_name not in tool_map:
                    result = f"Unknown tool: {tool_name}"
                else:
                    try:
                        result = tool_map[tool_name].invoke(tool_args)
                    except Exception as exc:
                        result = f"Tool error ({tool_name}): {exc}"

                messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_id)
                )

        # Exceeded max iterations
        last = messages[-1]
        if isinstance(last, AIMessage):
            return last.content or "(Explore Agent reached iteration limit)"
        return "(Explore Agent reached iteration limit without a final answer)"

    return explore_agent
