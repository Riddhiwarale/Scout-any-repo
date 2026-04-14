# Let's Understand the Bash Tool (Read-Only Version)

## What It Does
**Bash** executes shell commands on the system. Use it for terminal operations that **can't be done with other tools**.

- Runs shell commands with optional timeout
- Working directory persists between commands
- Shell state (environment variables, etc.) does NOT persist
- Initialized from user's shell profile (bash or zsh)

## Parameters

| Parameter | Purpose | Required |
|-----------|---------|----------|
| `command` | The command to execute | Yes |
| `timeout` | Max time in ms (default: 120000, max: 600000) | No |
| `description` | What the command does | No |
| `run_in_background` | Run without waiting for result | No |

## Read-Only Operations (Safe)

| Use Case | Example |
|----------|---------|
| **Git info** | `git status`, `git log`, `git diff`, `git branch` |
| **Directory listing** | `ls`, `ls -la`, `tree` |
| **Check versions** | `node -v`, `python --version`, `npm -v` |
| **Find executables** | `which node`, `where python` |
| **Environment info** | `pwd`, `whoami`, `env` |
| **Process info** | `ps`, `docker ps` |
| **Network info** | `curl -I https://example.com` (headers only) |
| **GitHub CLI** | `gh pr list`, `gh issue view 123` |

## Do NOT Use Bash For These

| Operation | Use This Tool Instead |
|-----------|----------------------|
| Read file contents | **Read** |
| Search file contents | **Grep** |
| Find files by pattern | **Glob** |
| Create/write files | **Write** |
| Edit files | **Edit** |
| Communicate with user | Just output text directly |

## Why Prefer Specialized Tools?

1. **Better user experience** - Specialized tools show progress, handle errors gracefully
2. **Safer** - No accidental side effects
3. **More efficient** - Optimized for their specific task
4. **Permissions** - Specialized tools have correct access

## Chaining Read-Only Commands

```bash
git log --oneline -10 && git status
```

| Operator | Behavior |
|----------|----------|
| `&&` | Run next only if previous succeeds |
| `;` | Run next regardless of previous result |
| `\|` | Pipe output to next command |

## Running in Background

Set `run_in_background: true` for long-running commands:
```
command: "npm test"
run_in_background: true
```
- Returns task ID immediately
- Use `TaskOutput` tool to check results later

## Important Notes

- Always use **absolute paths** when possible
- Quote paths with spaces: `"/path with spaces/"`
- Avoid `cd` - prefer absolute paths
- Never use interactive flags (`-i`) - not supported
- Output over 30k characters gets truncated
- Default timeout: 2 minutes, max: 10 minutes
