# Symbol Extractor Tool

## What It Is

A custom-built tool that takes a **file path** and returns a **table of contents** for that file — every function, class, and method name along with their exact **start and end line numbers**.

Implemented using **tree-sitter**, which parses source code into an AST (Abstract Syntax Tree), giving language-aware, precise symbol boundaries.

---

## The Problem It Solves

Without it, the agent's workflow for reading a function looks like this:

1. Grep finds `processPayment` at **line 340**
2. Agent calls Read with limit 50 — but the function is 200 lines long
3. Agent reads again with a higher limit
4. Maybe reads again

That's **3 tool calls** just to read one function, and it's still guessing.

With Symbol Extractor:

1. Grep finds `processPayment` at line 340
2. Symbol Extractor says: `processPayment` → **lines 340–541**
3. Agent calls Read **once**, exactly lines 340–541

Done in **one read call**, no guessing.

---

## Arguments

**Required:**

| Argument | Type | Description |
|---|---|---|
| `file_path` | string | Absolute or relative path to the source file |

**Optional:**

| Argument | Type | Description |
|---|---|---|
| `symbol_type` | string | Filter by `"function"`, `"class"`, `"method"` — defaults to all |
| `name_filter` | string | Return only symbols matching a name pattern |

---

## Output Format

A structured list — a table of contents for the file:

```
Symbol Name          | Type     | Start Line | End Line
---------------------|----------|------------|----------
processPayment       | function | 340        | 541
validateCard         | function | 120        | 158
PaymentHandler       | class    | 85         | 600
  __init__           | method   | 87         | 102
  refund             | method   | 210        | 265
```

Each entry gives:
- **Symbol name** — exact identifier as written in code
- **Type** — function, class, or method
- **Start line** — first line of the definition
- **End line** — last line (closing bracket/dedent)

---

## When TO Use It

**When you know the file but not the line range:**
Grep found the symbol in a file — now use Symbol Extractor to get exact lines, then Read once.

**When exploring a large unfamiliar file:**
Get a full map of what functions/classes exist before reading anything.

**When targeting a method inside a class:**
Classes can span hundreds of lines. Symbol Extractor shows which methods exist and where, so you read only what you need.

---

## When NOT To Use It

**When grep already gave you a tight enough target:**
If the symbol is visibly small from context — just Read directly. Symbol Extractor adds an extra round trip for no gain.

**On config or data files:**
JSON, YAML, `.env`, Markdown — tree-sitter finds no symbols. Use Read directly.

**For cross-file symbol search:**
It only scans one file at a time. Use Grep first to locate the file, then Symbol Extractor on the result.

**On minified or auto-generated files:**
Minified JS or generated protobuf files have meaningless symbol names. The output won't help the agent reason usefully.

---

## Decision Rule

```
Do I know which file?
├── No  → Grep first
└── Yes → Do I know the line range?
          ├── Yes, it's small → Read directly
          └── No / it's large → Symbol Extractor → then Read
```

---

## Why Tree-Sitter Over ctags

| | ctags | tree-sitter |
|---|---|---|
| Parsing | Regex-based | True AST parsing |
| Accuracy | Can miss nested functions | Precise, language-aware |
| Language support | Broad but shallow | Deep, with grammar packages per language |

Tree-sitter understands the *structure* of the code, not just patterns in text.
