# Let's Understand the Glob Tool

## What It Does
**Glob** is a fast file pattern matching tool. It finds files by **name/path patterns** (not contents).

- Returns matching file paths sorted by modification time (newest first)
- Works efficiently with any codebase size

## Pattern Syntax

| Pattern | Matches |
|---------|---------|
| `*.js` | All `.js` files in current directory |
| `**/*.js` | All `.js` files recursively in all subdirectories |
| `src/**/*.ts` | All `.ts` files under `src/` |
| `**/*.{ts,tsx}` | All `.ts` and `.tsx` files |
| `**/test*` | Files/folders starting with "test" |
| `src/components/*.tsx` | `.tsx` files directly in `src/components/` |

## Key Symbols

| Symbol | Meaning |
|--------|---------|
| `*` | Matches any characters (within a single directory level) |
| `**` | Matches any directories (recursive) |
| `?` | Matches a single character |
| `{a,b}` | Matches either `a` or `b` |

## When to Use Glob

1. **Finding specific file types** - "Find all Python files in this project"
2. **Locating config files** - Looking for `*.config.js`, `*.json`, etc.
3. **Finding files by name pattern** - "Where are all the test files?"
4. **Quick file discovery** - When you know roughly what the file is named

## When NOT to Use Glob

| Scenario | Use Instead |
|----------|-------------|
| Searching file contents | **Grep** |
| Open-ended exploration | **Task tool with Explore agent** |
| Reading a known file | **Read** directly |

## Example

If you ask "find all TypeScript files in src/", I'd run:
```
Glob: pattern="src/**/*.ts"
```

## Important Note

Glob matches **filenames only**, not file contents.

If a file is named `mm.py` but contains memory-related code, Glob with `*memory*` will NOT find it. Use Grep for content search.

## Glob vs Grep

| Glob | Grep |
|------|------|
| Searches **filenames** | Searches **file contents** |
| `**/memory*.ts` finds `memoryStore.ts` | `pattern: "memory"` finds files containing "memory" |
| Fast for known file patterns | Essential for finding code/text |
