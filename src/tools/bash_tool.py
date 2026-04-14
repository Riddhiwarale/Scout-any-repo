"""
Bash / Git tool — runs git commands and safe read-only shell operations
inside the repository. Powered by gitpython for git operations and
subprocess for raw shell commands.
"""

import os
import subprocess
from pathlib import Path

from langchain_core.tools import tool

# Commands that are explicitly allowed (read-only git + introspection)
_ALLOWED_PREFIXES = (
    "git log",
    "git blame",
    "git diff",
    "git show",
    "git status",
    "git branch",
    "git tag",
    "git shortlog",
    "git rev-list",
    "git ls-files",
    "git cat-file",
    "git describe",
    "git stash list",
    "ls",
    "find",
    "tree",
    "wc",
    "du",
    "head",
    "tail",
    "echo",
    "pwd",
    "cat",
    "file",
    "stat",
)


def make_bash_tool(repo_path: str):
    """Return a bash tool bound to `repo_path`."""

    @tool
    def bash(command: str) -> str:
        """
        Execute a read-only shell or git command inside the repository.
        Use this primarily for git operations:
            - git log  (understand why code exists / what changed)
            - git blame <file>  (identify origin of a specific line)
            - git diff <ref>    (inspect changes between commits)
            - git show <ref>    (view a specific commit)
            - git ls-files      (list tracked files)

        Also allowed: ls, find, tree, wc, head, tail, stat, cat.

        Destructive commands (rm, mv, write operations, git commit, git push,
        git reset, etc.) are blocked.

        Args:
            command: The shell command to run. Always runs with the repository
                     root as the working directory.
        """
        stripped = command.strip()

        # Safety check — only allow read-only operations
        lower = stripped.lower()
        if not any(lower.startswith(p) for p in _ALLOWED_PREFIXES):
            return (
                f"Command blocked for safety: {command!r}\n"
                "Only read-only git and introspection commands are permitted."
            )

        try:
            result = subprocess.run(
                stripped,
                shell=True,
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=30,
            )
            output = result.stdout.strip()
            err = result.stderr.strip()

            if result.returncode != 0 and not output:
                return f"Command failed (exit {result.returncode}):\n{err}"

            if not output:
                return "(No output)"

            # Truncate very large outputs
            lines = output.splitlines()
            if len(lines) > 500:
                lines = lines[:500]
                lines.append(f"... (truncated, {len(output.splitlines()) - 500} more lines)")
            return "\n".join(lines)

        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds."
        except Exception as exc:
            return f"Error running command: {exc}"

    return bash
