# The Explore Agent

## What It Is
A specialized subagent launched via the Task tool, designed for open-ended codebase exploration.

## How to Use It
```
Task tool with subagent_type="Explore"
```

## What It Does Internally
The Explore agent uses **Glob and Grep internally**, but in an iterative loop:

```
1. Start with a hypothesis (e.g., grep for "memory")
2. Get results → read promising files
3. Learn from what it finds → refine the search
4. Repeat until it understands the full picture
5. Return a synthesized answer
```

## Why Use Explore Agent vs Direct Glob/Grep

| Direct Glob/Grep | Explore Agent |
|------------------|---------------|
| One search per turn | Multiple searches in one turn |
| You must guess the right pattern | It can try multiple patterns |
| Returns raw file list/matches | Returns understanding + context |
| You see results, then must search again | It iterates autonomously |

## How It Finds Badly Named Files

Even if a file is named `mm.py` instead of `memory.py`:

1. **Grep for the concept** - Search file contents for "memory", "remember", "cache"
2. **Follow the trail** - Find where it's imported/used, trace the code path
3. **Search for related terms** - Error messages, comments, variable names

Example:
```
grep "memory"           → finds: from mm import MemoryStore
grep "MemoryStore"      → finds: mm.py:12
read mm.py              → now we understand it
```

## Key Insight
- **Glob** = find by filename pattern
- **Grep** = find by file contents

For exploration, **Grep is more reliable** because code contains descriptive words even when filenames don't.

## Tools Available to Explore Agent
All tools **except**: Task, Edit, Write, NotebookEdit, ExitPlanMode

It can search and read, but cannot modify anything - purely for investigation.
