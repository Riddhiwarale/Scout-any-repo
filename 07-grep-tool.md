# Let's Understand the Grep Tool

## What It Does
**Grep** searches **file contents** using regex patterns. It's built on `ripgrep` (rg), which is fast and powerful.

- Searches inside files for text/patterns
- Supports full regex syntax
- Can filter by file type or glob pattern
- Returns matching files, lines, or counts

## Output Modes

| Mode | What It Returns |
|------|-----------------|
| `files_with_matches` (default) | Just file paths that contain matches |
| `content` | Actual matching lines with context |
| `count` | Number of matches per file |

## Key Parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `pattern` | Regex to search for | `"function.*memory"` |
| `path` | Where to search | `"src/"` |
| `glob` | Filter files by pattern | `"*.ts"` |
| `type` | Filter by file type | `"js"`, `"py"`, `"rust"` |
| `-i` | Case insensitive | `true` |
| `-C` | Context lines (before & after) | `3` |
| `-A` | Lines after match | `5` |
| `-B` | Lines before match | `5` |

## Pattern Syntax (Regex)

| Pattern | Matches |
|---------|---------|
| `memory` | Literal word "memory" |
| `memory.*store` | "memory" followed by anything, then "store" |
| `function\s+\w+` | "function" + whitespace + word |
| `log.*Error` | "log" ... "Error" on same line |
| `import.*from` | Import statements |
| `class\s+\w+` | Class definitions |

## Common Regex Symbols

| Symbol | Meaning |
|--------|---------|
| `.` | Any single character |
| `*` | Zero or more of previous |
| `+` | One or more of previous |
| `?` | Zero or one of previous |
| `\s` | Whitespace |
| `\w` | Word character (a-z, A-Z, 0-9, _) |
| `\d` | Digit (0-9) |
| `\b` | Word boundary |
| `^` | Start of line |
| `$` | End of line |
| `[abc]` | Any of a, b, or c |
| `[^abc]` | Not a, b, or c |
| `(a\|b)` | Either a or b |

## Examples

**Find files containing "memory":**
```
pattern: "memory"
output_mode: "files_with_matches"
```

**Find function definitions with context:**
```
pattern: "function loadMemory"
output_mode: "content"
-C: 5
```

**Search only TypeScript files:**
```
pattern: "useState"
type: "ts"
```

**Case-insensitive search:**
```
pattern: "error"
-i: true
```

## Multiline Matching

By default, patterns match within single lines. For patterns spanning lines:
```
pattern: "struct \\{[\\s\\S]*?field"
multiline: true
```

## When to Use Grep

1. **Finding definitions** - Where is a function/class defined?
2. **Finding usages** - Where is this function called?
3. **Finding imports** - What files import this module?
4. **Searching strings** - Find error messages, comments, logs
5. **Code patterns** - Find all TODO comments, all async functions, etc.

## Grep vs Glob

| Glob | Grep |
|------|------|
| Searches **filenames** | Searches **file contents** |
| `**/memory*.ts` finds `memoryStore.ts` | `pattern: "memory"` finds files containing "memory" |
| Fast for known file patterns | Essential for finding code/text |

## Important Notes

- Pattern uses **ripgrep syntax** (not standard grep)
- Literal braces need escaping: use `interface\{\}` to find `interface{}`
- Always use Grep tool, never `grep` or `rg` via Bash
- For open-ended exploration, use Explore agent (which uses Grep internally)
