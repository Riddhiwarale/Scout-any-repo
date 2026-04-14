# Let's Understand the Read Tool

## What It Does
**Read** reads file contents from the filesystem. It's the simplest and most direct way to view what's inside a file.

- Reads any file and returns its contents
- Shows line numbers (like `cat -n`)
- Can read partial files (offset + limit)
- Handles multiple file types: code, text, images, PDFs, Jupyter notebooks

## Parameters

| Parameter | Purpose | Required |
|-----------|---------|----------|
| `file_path` | Absolute path to the file | Yes |
| `offset` | Line number to start from | No |
| `limit` | Number of lines to read | No |

## Default Behavior

- Reads up to **2000 lines** from the start
- Lines longer than **2000 characters** are truncated
- Line numbers start at **1**

## Special File Types

| Type | What Happens |
|------|--------------|
| **Images** (PNG, JPG, etc.) | Displayed visually (Claude is multimodal) |
| **PDFs** | Processed page by page, extracts text + visuals |
| **Jupyter notebooks** (.ipynb) | Returns all cells with outputs |
| **Empty files** | Returns a system warning |

## Examples

**Read entire file:**
```
file_path: "/src/index.ts"
```

**Read lines 100-200 of a large file:**
```
file_path: "/src/bigFile.ts"
offset: 100
limit: 100
```

**Read an image:**
```
file_path: "/screenshots/error.png"
```

## When to Use Read

1. **You know the exact file path** - Direct, fastest option
2. **Viewing file contents** - After finding files with Glob/Grep
3. **Reading images/screenshots** - Claude can analyze them visually
4. **Reading documentation** - PDFs, markdown files

## When NOT to Use Read

| Scenario | Use Instead |
|----------|-------------|
| Don't know which file to read | **Glob** or **Grep** first |
| Want to read a directory listing | **Bash** with `ls` |
| Open-ended exploration | **Explore agent** |

## Read vs Other Tools

| Tool | Purpose |
|------|---------|
| **Read** | View contents of a known file |
| **Glob** | Find files by name pattern |
| **Grep** | Find files by contents |
| **Bash cat/head/tail** | Don't use - Read is preferred |

## Important Notes

- Path must be **absolute**, not relative
- Can read files that don't exist (returns error, doesn't crash)
- For directories, use `ls` via Bash instead
- Multiple files can be read in parallel for efficiency
