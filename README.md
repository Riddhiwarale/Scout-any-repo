# Scout — AI Agent for GitHub Repository Q&A

> Ask natural language questions about any codebase. Get precise, code-cited answers powered by a multi-agent ReAct system.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-orange)
![Groq](https://img.shields.io/badge/Groq-LLaMA%203-red?logo=meta&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST%20%2B%20SSE-green?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## What It Does

Scout is an **agentic AI system** that answers questions about any GitHub repository in natural language. It understands code the way a senior engineer would — by actually reading files, searching for definitions, tracing cross-file references, and consulting git history.

```
You:   "How does authentication flow from the API into the database?"
Scout: Reads auth.py → traces imports → reads db/session.py → reads middleware →
       returns a precise, file-cited explanation of the entire flow.
```

No RAG. No vector databases. No pre-indexing. Just an agent with the right tools.

---

## Why Not RAG?

Most codebase Q&A tools use Retrieval-Augmented Generation (RAG): embed all files into a vector database and retrieve "similar" chunks at query time. This works for documents, but breaks for code.

| Problem with RAG | How Scout solves it |
|---|---|
| Chunking splits functions across boundaries | Agent reads exact line ranges |
| Embedding similarity ≠ code precision | Grep finds by name with 100% precision |
| Re-indexing required after every commit | Agent reads files directly from disk — always current |
| Can't trace call graphs across files | Agent follows imports dynamically in a single query |

Scout uses an **agentic approach**: no upfront indexing, exact search, dynamic cross-file tracing, always up-to-date.

---

## Architecture

### The ReAct Pattern

Scout is built around the **ReAct** (Reason + Act) loop — the same pattern used in state-of-the-art AI agents.

```
┌─────────────────────────────────────────────────┐
│                  ReAct Loop                     │
│                                                 │
│   1. REASON  →  What do I need to find?         │
│   2. ACT     →  Call a tool (grep / read / ...) │
│   3. OBSERVE →  Process the result              │
│   4. REPEAT  →  Until I have enough information │
│   5. RESPOND →  Synthesize a final answer       │
└─────────────────────────────────────────────────┘
```

This allows the agent to adapt mid-query. If a grep returns no results, it reasons about alternative search terms and tries again — rather than silently returning nothing.

---

### Two-Agent System

Scout uses a **tiered, two-agent architecture** to balance reasoning quality with execution cost.

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│              Orchestrator Agent                             │
│              Model: llama-3.3-70b-versatile (Groq)         │
│              Role:  Plan, reason, decide, synthesize        │
│                                                             │
│   Simple query?  ──► Call tools directly                   │
│   Complex query? ──► Spawn Explore Agent                   │
└───────────────────────────┬─────────────────────────────────┘
                            │ (complex queries only)
                            ▼
              ┌─────────────────────────────┐
              │       Explore Agent         │
              │  Model: llama-3.1-8b-instant│
              │  Role:  Deep investigation  │
              │                             │
              │  Runs its own ReAct loop    │
              │  10-15 tool calls if needed │
              │  Returns structured summary │
              └─────────────────────────────┘
```

**Why two agents?**
- The **Orchestrator** (70B) handles high-level reasoning and planning. This needs a capable model.
- The **Explore Agent** (8B) handles execution — running grep, reading files, following references. A fast, lightweight model is perfect here.
- This **cuts cost and latency** on the tool-execution loop while preserving quality where it matters.

---

### Full System Flow

```
                    ┌──────────────────────────────────────────┐
                    │           LangGraph State Graph          │
                    └──────────────────────────────────────────┘

  User Query + History
         │
         ▼
  ┌─────────────┐     tool_calls?     ┌──────────────┐
  │Orchestrator │ ──── Yes ─────────► │  Tool Node   │
  │   (Sonnet)  │ ◄───────────────── │  (6 tools)   │
  └──────┬──────┘    results          └──────────────┘
         │
         │ No tool_calls (final answer)
         ▼
  ┌──────────────┐   tokens < 70%    ┌──────────────┐
  │   Context    │ ──── OK ────────► │     END      │
  │   Monitor   │                    └──────────────┘
  └──────┬───────┘
         │ tokens ≥ 70%
         ▼
  ┌──────────────┐
  │  Compactor   │  ──► Replaces raw history with structured summary
  │  (8b model)  │  ──► Conversation continues without context overflow
  └──────────────┘
```

---

### The 6 Tools

Every tool call in Scout is exact and deterministic — no semantic guessing.

| Tool | Purpose | Why it matters |
|---|---|---|
| **Grep** | Regex search via ripgrep | Finds any function/class/variable with 100% precision. No false positives from embedding drift. |
| **Glob** | File discovery by pattern | Navigates repo structure before reading. Confirms files exist. Finds all files of a type. |
| **Read** | File content with line ranges | Reads only the lines needed — not the full file. Keeps context window clean. |
| **Bash** | Read-only git commands | `git log`, `git blame`, `git diff` — answers *why* code exists, not just *what* it does. |
| **Symbol Extractor** | AST-level symbol table via tree-sitter | Returns every function/class with exact start/end lines. Eliminates multi-read guessing for large files. |
| **Explore Agent** | Delegates to the Haiku sub-agent | For complex, cross-file queries. Absorbs tool-call noise from the Orchestrator's context. |

---

### Context Management

Long conversations eventually fill the model's context window. Scout handles this automatically.

**Context Monitor** — runs silently after every turn, counts tokens.

**Compactor** — triggers at **70% of the context window**. It:
1. Summarizes the full conversation history with a structured prompt
2. Preserves: original user goal, files examined, key findings, conclusions reached, last few exchanges verbatim
3. Prunes: failed tool calls, duplicate findings, intermediate dead ends
4. Replaces the raw history with the compressed summary
5. **Blocks the next user turn** until compression is complete (guarantees consistency)

The conversation can continue indefinitely without degrading quality.

---

## Tech Stack

| Component | Technology |
|---|---|
| Agent Orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) — StateGraph with conditional edges |
| Orchestrator LLM | `llama-3.3-70b-versatile` via [Groq](https://groq.com) |
| Explore / Compactor LLM | `llama-3.1-8b-instant` via Groq |
| LLM Integration | [langchain-groq](https://python.langchain.com/docs/integrations/chat/groq) |
| Code Search | ripgrep (`rg`) with pure-Python fallback |
| Symbol Extraction | [tree-sitter](https://tree-sitter.github.io/) — AST-level parsing, 8 languages |
| Git Context | subprocess (`git log`, `blame`, `diff`) |
| Token Counting | [tiktoken](https://github.com/openai/tiktoken) |
| API Server | [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) |
| Streaming | Server-Sent Events (SSE) via [sse-starlette](https://github.com/sysid/sse-starlette) |
| Config | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) + python-dotenv |

---

## Getting Started

### Prerequisites

- Python 3.10+
- A free [Groq API key](https://console.groq.com) (no credit card required)
- ripgrep installed (`winget install BurntSushi.ripgrep.MSVC` on Windows, `brew install ripgrep` on Mac)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/Riddhiwarale/Scout-any-repo.git
cd Scout-any-repo

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Open .env and set your GROQ_API_KEY
```

### Run

```bash
# Interactive multi-turn REPL
python -X utf8 main.py --repo /path/to/any/cloned/repo

# Single question
python -X utf8 main.py --repo /path/to/repo --ask "How does X work?"

# REST API server
python main.py --serve
```

---

## API Reference

Start the server with `python main.py --serve`, then:

### `POST /chat`
Non-streaming. Returns the full answer once the ReAct loop completes.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does the authentication middleware do?",
    "repo_path": "/path/to/repo",
    "session_id": null
  }'
```

```json
{
  "answer": "The authentication middleware...",
  "session_id": "abc-123",
  "token_count": 1842
}
```

### `POST /chat/stream`
Streaming via Server-Sent Events. Streams tokens as they are generated.

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "...", "repo_path": "/path/to/repo"}'
```

### `DELETE /session/{id}`
Clear conversation history for a session.

---

## Project Structure

```
Scout-any-repo/
├── main.py                     # CLI entry point (REPL + single-ask + --serve)
├── requirements.txt
├── .env.example
│
├── src/
│   ├── config.py               # Pydantic settings (models, thresholds, API keys)
│   │
│   ├── tools/
│   │   ├── grep_tool.py        # ripgrep wrapper with pure-Python fallback
│   │   ├── glob_tool.py        # pathlib file discovery
│   │   ├── read_tool.py        # Line-range file reader (+ notebook / PDF support)
│   │   ├── bash_tool.py        # Read-only git & shell commands
│   │   └── symbol_extractor.py # tree-sitter AST symbol table (+ regex fallback)
│   │
│   ├── agents/
│   │   └── explore_agent.py    # Haiku-powered sub-agent as a LangChain @tool
│   │
│   └── graph/
│       ├── state.py            # AgentState TypedDict (extends MessagesState)
│       ├── prompts.py          # Orchestrator + Compactor system prompts
│       ├── nodes.py            # All node functions + routing logic
│       └── react_graph.py      # build_graph() + ask() convenience wrapper
│
└── api/
    └── main.py                 # FastAPI: /chat, /chat/stream, /session
```

---

## Example Questions

```
"What does the payment processing flow look like end-to-end?"
"Where is the database connection pool initialized and configured?"
"Which files import the AuthMiddleware class?"
"What changed in the last 5 commits to the API layer?"
"How does data flow from the REST endpoint into the database?"
"What does the processOrder function do, and what calls it?"
"Are there any TODO comments in the codebase?"
```

---

## How the ReAct Loop Works in Practice

Here's a real example of the agent's internal reasoning for the question *"How does user login work?"*:

```
[REASON]  I need to find where login is handled. I'll grep for "login".
[ACT]     grep(pattern="def login|login_user|/login")
[OBSERVE] Found: auth/views.py:45, api/routes.py:112

[REASON]  Let me see the full login function. I'll extract symbols first.
[ACT]     extract_symbols("auth/views.py")
[OBSERVE] login_user: lines 45–89, requires_auth: lines 91–102

[REASON]  Now read the exact function.
[ACT]     read("auth/views.py", offset=45, limit=44)
[OBSERVE] It calls authenticate(), then creates a JWT token via token_service.

[REASON]  I need to understand authenticate(). Let me find it.
[ACT]     grep(pattern="def authenticate")
[OBSERVE] Found: auth/service.py:23

[ACT]     read("auth/service.py", offset=23, limit=30)
[OBSERVE] Queries the DB, checks bcrypt hash, returns user object.

[REASON]  I have enough to give a complete answer.
[RESPOND] "User login works as follows: ..."
```

No guessing. No semantic similarity. Every step is exact.

---

## License

MIT — use it, fork it, build on it.

---

*Built with [LangGraph](https://github.com/langchain-ai/langgraph), [Groq](https://groq.com), and the ReAct pattern.*
