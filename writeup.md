# GitHub Repository Q&A Agent — Architecture Write-Up

---

## 1. Overview

The agentic AI system is capable of answering natural language questions about any GitHub repository. The system understands the complete codebase — functions, classes, modules, and their relationships across files — and interacts with users in a conversational, multi-turn manner.

The core design decision is to use an **agentic, tool-based architecture** rather than a Retrieval-Augmented Generation (RAG) pipeline. This choice is deliberate and justified in detail below. The system is built around two LLM agents operating in a ReAct (Reason + Act) loop, a suite of six purpose-built tools, and a context management layer that ensures the system remains efficient as conversations grow.

---

## 2. Architectural Approach: Why Agentic over RAG

The most common approach to codebase Q&A is RAG: embed all files into a vector database, retrieve semantically similar chunks at query time, and pass them to an LLM for synthesis. While RAG works well for static document corpora, it has fundamental limitations when applied to codebases.

### 2.1 Limitations of RAG for Code

- **Chunking loses context:** Splitting code into chunks often breaks dependencies like imports, helper functions, and references across files.

- **Embedding context is too small:** Large files still need to be split because embedding models have limited token windows compared to modern LLMs.

- **Reindexing is expensive:** Frequent code changes require continuous re-embedding and vector DB updates, increasing compute cost over time.

- **Weak cross-file reasoning:** RAG struggles to follow call chains and data flow across multiple files, unlike agent-based approaches.

### 2.2 Why Agentic Works Better for Code

An agentic system does not pre-index anything. Instead, it navigates the repository on demand using a set of tools — the same way a skilled developer would explore an unfamiliar codebase. It uses exact search (grep) rather than semantic similarity, reads files at precise line ranges, and follows cross-file references dynamically.

Key advantages:
- **No upfront indexing cost** — the system pays only when a query is made
- **Exact, deterministic retrieval** — grep finds a function by name with 100% precision; no false positives from semantic drift
- **Dynamic cross-file tracing** — the agent can follow import chains, trace call graphs, and correlate definitions across files in a single query
- **Always up to date** — since the agent reads files directly from disk, it always sees the current state of the codebase with no reindexing required
- **Self-correcting** — if a tool call returns no results, the agent can reason about why and try a different approach

---

## 3. System Components

### 3.1 Orchestrator Agent — Sonnet (ReAct Agent)

The Orchestrator is the central reasoning component of the system. It receives the user's query, reasons about how to answer it, decides which tools to invoke or whether to delegate to the Explore Agent, synthesizes results, and generates the final response.

**Model: Claude Sonnet**
Sonnet is chosen for the Orchestrator because it offers strong reasoning capability. The Orchestrator's job is to plan — to decompose a question into a sequence of tool calls and reason over their outputs. This requires genuine language understanding and multi-step reasoning, which lighter models handle less reliably.

**Pattern: ReAct (Reason + Act)**
The Orchestrator operates in a ReAct loop:
1. **Reason** — think about what information is needed
2. **Act** — call a tool or spawn the Explore Agent
3. **Observe** — process the tool result
4. **Repeat** until enough information is gathered
5. **Respond** — synthesize a final answer for the user

This pattern allows the system to adapt mid-query. If an initial grep returns no results, the Orchestrator can reason about alternative search terms or locations, rather than failing silently the way a RAG pipeline would.

**Decision: Simple vs Complex Queries**
The Orchestrator is guided by rules in its system prompt to distinguish between query types:
- **Simple query** → answer can likely be found in one or two targeted tool calls (e.g., "what does function X do?")
- **Complex / cross-file query** → requires tracing logic across multiple files (e.g., "how does data flow from the API into the UI?")

For simple queries, the Orchestrator calls tools directly. For complex queries, it delegates to the Explore Agent.

---

### 3.2 Explore Agent — Haiku (ReAct Agent)

The Explore Agent is a secondary ReAct agent that handles deep, multi-step codebase investigations. It operates independently, runs its own tool-calling loop, and returns a single structured summary to the Orchestrator.

**Model: Claude Haiku**
Haiku is a lightweight, fast, and cost-efficient model. Since the Explore Agent's job is execution — running grep, reading files, following references — rather than high-level reasoning, Haiku is well-suited for the task. This tiered model strategy (Sonnet reasons, Haiku executes) significantly reduces the cost per query while maintaining quality where it matters.

**One-shot output**
The Explore Agent is not conversational with the Orchestrator. It receives a detailed brief, completes its investigation autonomously, and returns one summary. This keeps the Orchestrator's context window clean and prevents tool-call noise from polluting the main conversation thread.

**Why a separate agent and not just more tool calls?**
For complex queries, the investigation may require 10-15 tool calls across many files. If the Orchestrator handled all of these directly, its context window would fill up with raw tool outputs — leaving less room for conversation history and the final synthesis. The Explore Agent absorbs this noise and hands back only what is useful.

---

### 3.3 Tool Layer

The system has six tools available to both the Orchestrator and the Explore Agent.

#### Grep
Searches file contents using regex, powered by ripgrep. This is the primary tool for finding where a function, class, variable, or pattern is defined or used. Returns matching lines with file paths and line numbers. Supports filtering by file type, context lines around matches, and case-insensitive search.

*Justification:* Exact string/regex search is more reliable than semantic similarity for code lookups. "Find all usages of `processPayment`" has a definitive answer via grep; RAG would return probabilistic guesses.

#### Glob
Finds files by name or path pattern. Used to explore the repository structure, find all files of a given type, or check whether a specific file or directory exists.

*Justification:* Before reading a file, the agent often needs to confirm it exists or discover which files in a directory are relevant. Glob is the correct tool for structural navigation.

#### Read
Reads file contents with optional offset and line range. Returns content with line numbers, enabling precise targeted reading. Supports text files, images, PDFs, and Jupyter notebooks.

*Justification:* Once a target file and line are identified (via Grep), Read retrieves the exact content needed. By using offset and limit, the agent avoids loading large files into context unnecessarily — only the relevant sections are read.

#### Bash
Executes shell commands. Used primarily for git operations: `git log` to understand why code exists and what changed recently, `git blame` to identify the origin of a specific line, and `git diff` to inspect recent changes.

*Justification:* Code understanding is not just about *what* the code does — it's also about *why* it exists and *what changed*. Git history provides this context. No other tool covers this.

#### Symbol Extractor
A custom-built tool (implemented via ctags or tree-sitter) that takes a file path and returns all function, class, and method names along with their start and end line numbers — a table of contents for any source file.

*Justification:* Without this tool, reading a function requires guessing how many lines it spans. The typical flow is: grep to find line 340, read with an arbitrary limit of 50 lines, then read again if the function continues. Symbol Extractor eliminates this guesswork entirely — the agent knows that `processMatchData` runs from line 340 to line 541 and can read it exactly in one call. This reduces read operations significantly for large files.

#### Explore Agent (as a tool)
The Orchestrator invokes the Explore Agent as a tool call, passing a detailed prompt. From the Orchestrator's perspective, it is simply a tool that takes a question and returns a summary.

---

### 3.4 Conversation History (Message Array)

The conversation history is a running array of all messages in the current session: user queries, agent responses, and tool call summaries. It is passed to the Orchestrator at the start of every turn, giving the agent full context of what has been discussed.

This enables multi-turn conversations where users can ask follow-up questions, refer to previous answers, and refine their queries naturally — the same way they would with a human developer.

---

### 3.5 Context Monitor

The Context Monitor tracks the current size of the conversation history relative to the model's context window. It runs passively after every turn and checks whether the conversation is approaching the context limit.

**Threshold: 70%**
At 70% of the context window, the Compactor is automatically triggered. This threshold is chosen to leave enough headroom for the Compactor's own output, the next user query, and the agent's tool calls — while ensuring compression happens before the system silently degrades from context overflow.

---

### 3.6 Compactor

The Compactor is a compression component that runs automatically when the 70% threshold is crossed. It replaces the raw conversation history with a structured summary, freeing up context window space for the conversation to continue.

**Blocking behavior**
The Compactor runs at the end of a turn, before the user is allowed to send the next message. This is critical: if a new question arrived mid-compression, the summary would not include the new question's answer, making the compression inconsistent. Blocking ensures the summary is always coherent and complete before the next turn begins.

**System prompt-guided summarization**
The Compactor operates under a system prompt that specifies exactly what to preserve:
- The original user question and overall intent of the conversation
- Files that were read and their key findings
- Functions or classes that were identified as relevant
- Decisions or conclusions already reached
- The most recent few exchanges verbatim (for continuity)

**Pruning failed tool calls**
Intermediate tool calls that did not yield useful results (e.g., a grep that returned no matches before a successful one was found) are pruned from the summary. Only successful, information-bearing tool calls are preserved. This further reduces context consumption without losing useful information.

---

### 3.7 Repository Access

The repository is accessed directly from the local filesystem. The user provides a path — either by opening the tool inside a cloned repository folder or by specifying the path explicitly. No special ingestion, indexing, or preprocessing is required. The tool suite operates directly on the files as they exist on disk, meaning the system is always reading the current state of the code with zero setup overhead.

---

## 4. System Flow

The following describes a complete turn in the system from user query to response.

```
1. User submits a query

2. Query + full conversation history → Orchestrator (Sonnet)

3. Orchestrator reasons about what is needed to answer the query

4. Orchestrator classifies the query:
   ├── Simple (single target, 1-2 tool calls likely sufficient)
   │     └── Calls tools directly: Grep → Symbol Extractor → Read → Bash as needed
   │
   └── Complex (cross-file, requires multi-step investigation)
         └── Spawns Explore Agent (Haiku) with a detailed brief
               └── Explore Agent runs its own ReAct loop
               └── Returns one structured summary to Orchestrator

5. Orchestrator reviews tool / Explore Agent results
   ├── Needs more information → back to step 4
   └── Has sufficient information → proceed

6. Orchestrator generates final response
   └── Response delivered to user
   └── Conversation history updated

7. [BLOCKING] Context Monitor checks history size:
   ├── Below 70% → nothing, user can type next message
   └── Above 70% → Compactor triggers
         └── Summarizes history per system prompt rules
         └── Prunes failed/intermediate tool calls
         └── Replaces raw history with compressed summary
         └── User is unblocked, next turn begins
```

---

## 5. Key Technology Choices

| Component | Technology | Justification |
|-----------|-----------|---------------|
| Orchestrator | Claude Sonnet | Strong reasoning at practical cost; drives the ReAct planning loop |
| Explore Agent | Claude Haiku | Fast, cheap execution agent; handles high-frequency tool calls |
| Code search | ripgrep (via Grep tool) | Fastest available code search; exact regex matching; battle-tested |
| Symbol extraction | ctags / tree-sitter | Mature, language-aware AST parsing; gives precise line ranges per symbol |
| Git context | git CLI via Bash | Authoritative source for history, blame, and diff — no abstraction needed |
| Compression | LLM-based Compactor | Flexible, context-aware summarization guided by a system prompt; preserves what matters |

---


## 6. GitHub Repository Q&A Agent — Tech Stack

## Component-wise Tech Stack

| # | Component | Technology | Libraries / Tools | Notes |
|---|-----------|-----------------|-------------------|-------|
| 1 | **Orchestrator Agent** | Claude Sonnet 3.5 / Sonnet 3.7 | `anthropic` Python SDK, LangGraph (ReAct agent loop) | Use `claude-sonnet-3-7` for stronger multi-step planning; LangGraph handles the ReAct cycle natively |
| 2 | **Explore Agent** | Claude Haiku 3.5 | `anthropic` Python SDK, LangGraph (sub-graph) | Invoked as a child graph node; returns structured summary only |
| 3 | **Tool — Grep** | ripgrep (`rg`) | `subprocess` (Python), `ripgrepy` wrapper | Fastest regex search on large repos; supports file-type filtering and context lines |
| 4 | **Tool — Glob** | Python `glob` / `pathlib` | `pathlib.Path.rglob()` or `glob.glob()` | No external dependency needed; `pathlib` preferred for cross-platform compatibility |
| 5 | **Tool — Read** | Python `open()` / nbformat | `nbformat` (for `.ipynb`), `pypdf` (for PDFs), `Pillow` (for images) | Line-range reads handled via slicing; binary types need format-specific parsers |
| 6 | **Tool — Bash / Git** | `gitpython` or subprocess | `gitpython`, `subprocess` | `gitpython` for `git log`, `blame`, `diff`; raw subprocess for edge cases |
| 7 | **Tool — Symbol Extractor** | tree-sitter | `tree-sitter`, language grammar packages (e.g. `tree-sitter-python`, `tree-sitter-javascript`) | Preferred over ctags; produces AST-level precision with start/end line numbers per symbol |
| 8 | **Agent Orchestration Framework** | LangGraph | `langgraph`, `langchain-core` | Models Orchestrator + Explore Agent as a state graph; handles ReAct loop, tool dispatch, and sub-agent invocation cleanly |
| 9 | **Tool Schema & Dispatch** | LangChain Tools | `@tool` decorator or `StructuredTool` from `langchain_core.tools` | Defines each tool with JSON schema for function-calling; plugs directly into LangGraph nodes |
| 10 | **Conversation History** | LangGraph State | `MessagesState` / custom `TypedDict` state in LangGraph | Conversation array lives in graph state; passed into every node automatically |
| 11 | **Context Monitor** | Custom Python utility | `tiktoken` (token counting for OpenAI-compatible models), or Anthropic's token count API | Runs post-turn; compares current token count to model's context window limit |
| 12 | **Compactor** | Claude Haiku 3.5 (summarization call) | `anthropic` SDK, custom system prompt | Haiku used here for cost efficiency; takes raw message history, returns structured summary |
| 13 | **Repository Access** | Local filesystem | `pathlib`, `os` | No ingestion needed; tools operate directly on cloned repo path provided at startup |
| 14 | **API / Serving Layer** | FastAPI | `fastapi`, `uvicorn`, `pydantic` | Exposes the agent as a REST endpoint; supports streaming responses via SSE |
| 15 | **Streaming** | Server-Sent Events (SSE) | `fastapi-sse`, Anthropic streaming SDK | Streams Orchestrator token output to client in real-time |
| 16 | **Observability & Tracing** | Langfuse | `langfuse`, LangGraph callback integration | Traces each ReAct step, tool call, and sub-agent run; cost and latency monitoring |
| 17 | **Environment & Config** | Python dotenv | `python-dotenv`, `pydantic-settings` | Manages API keys, repo path, model names, and threshold configs |
---

## Model Selection Summary

| Agent | Model | Reason |
|-------|-------|--------|
| Orchestrator | Claude Sonnet 3.7 | Strong reasoning, multi-step planning, tool selection |
| Explore Agent | Claude Haiku 3.5 | Fast execution, cost-efficient, low-level tool calls |
| Compactor | Claude Haiku 3.5 | Summarization is straightforward; cost savings matter here |

---

## 7. Prompt Caching

Every API call in this system sends the same large static content on every turn: the Orchestrator's system prompt, all six tool schemas, and the accumulated conversation history. Without caching, these tokens are billed at full price on every single call. Prompt caching eliminates most of this cost.

### How It Works

The Anthropic API supports a `cache_control` flag on individual content blocks. Placing this marker on a block tells the server to cache everything up to and including that point. On subsequent calls where the prefix is identical, those tokens are served from cache at **90% cheaper than normal input price**.

Cache writes (first time a prefix is cached) cost 125% of normal input price — slightly more. But break-even arrives at the second call, and every call after that saves 90% on all cached tokens.

### What Gets Cached in Our System

| Content | Behaviour |
|---------|-----------|
| System prompt | Static across all turns — cached after the first call, 90% cheaper on every subsequent turn |
| Tool schemas (all 6 tools) | Static — cached after the first call, same saving |
| Conversation history | The cache marker is placed at the end of the last message on every call. On the next turn, all prior turns are already cached — only the new turn's tokens are billed at full price |

The compounding effect on conversation history is significant. By turn 10 with a 20K-token history, turns 1–9 are cached at 90% discount. You pay full price only for the ~500 new tokens in turn 10. The longer the conversation, the greater the saving.
