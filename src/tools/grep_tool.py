"""
Grep tool — searches file contents using ripgrep (rg).
Falls back to Python's re module if rg is not installed.
"""

import os
import re
import subprocess
from typing import Optional

from langchain_core.tools import tool


def make_grep_tool(repo_path: str):
    """Return a grep tool bound to `repo_path`."""

    @tool
    def grep(
        pattern: str,
        path: str = "",
        file_glob: str = "",
        file_type: str = "",
        case_insensitive: bool = False,
        context_lines: int = 0,
        output_mode: str = "content",
        multiline: bool = False,
    ) -> str:
        """
        Search file contents using ripgrep (rg). Use this to find where
        functions, classes, variables, or any pattern are defined or used.

        Args:
            pattern: Regex pattern to search for (ripgrep syntax).
            path: Sub-path inside the repo to restrict the search.
                  Leave empty to search the entire repo.
            file_glob: Glob filter for filenames, e.g. "*.py" or "**/*.ts".
            file_type: Ripgrep file type shorthand, e.g. "py", "js", "rust".
            case_insensitive: Perform a case-insensitive search.
            context_lines: Number of lines to show before AND after each match.
            output_mode: "content" (matching lines), "files" (file paths only),
                         or "count" (match count per file).
            multiline: Enable multiline mode so patterns can span lines.
        """
        search_root = os.path.join(repo_path, path) if path else repo_path

        # Try ripgrep first
        try:
            return _run_ripgrep(
                pattern,
                search_root,
                file_glob,
                file_type,
                case_insensitive,
                context_lines,
                output_mode,
                multiline,
            )
        except FileNotFoundError:
            # rg not installed — fall back to pure Python
            return _python_grep(
                pattern, search_root, file_glob, case_insensitive, context_lines
            )

    return grep


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _run_ripgrep(
    pattern: str,
    search_root: str,
    file_glob: str,
    file_type: str,
    case_insensitive: bool,
    context_lines: int,
    output_mode: str,
    multiline: bool,
) -> str:
    cmd = ["rg", "--no-heading"]

    if case_insensitive:
        cmd.append("-i")
    if multiline:
        cmd += ["-U", "--multiline-dotall"]
    if context_lines > 0:
        cmd += ["-C", str(context_lines)]
    if file_glob:
        cmd += ["--glob", file_glob]
    if file_type:
        cmd += ["--type", file_type]

    if output_mode == "files":
        cmd.append("-l")
    elif output_mode == "count":
        cmd.append("-c")
    else:
        cmd += ["-n"]  # line numbers for content mode

    cmd += [pattern, search_root]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stdout.strip()
    if not output:
        return f"No matches found for pattern: {pattern!r}"
    # Limit output to avoid flooding the context window
    lines = output.splitlines()
    if len(lines) > 300:
        lines = lines[:300]
        lines.append(f"... (truncated, {len(output.splitlines()) - 300} more lines)")
    return "\n".join(lines)


def _python_grep(
    pattern: str,
    search_root: str,
    file_glob: str,
    case_insensitive: bool,
    context_lines: int,
) -> str:
    """Pure-Python fallback when ripgrep is unavailable."""
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        return f"Invalid regex pattern: {exc}"

    results: list[str] = []
    for dirpath, _dirs, filenames in os.walk(search_root):
        for fname in filenames:
            if file_glob and not _match_glob(fname, file_glob):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
            except OSError:
                continue
            for i, line in enumerate(lines):
                if compiled.search(line):
                    rel = os.path.relpath(fpath, search_root)
                    snippet_start = max(0, i - context_lines)
                    snippet_end = min(len(lines), i + context_lines + 1)
                    for j in range(snippet_start, snippet_end):
                        marker = ">" if j == i else " "
                        results.append(
                            f"{rel}:{j + 1}{marker} {lines[j].rstrip()}"
                        )
                    if len(results) > 500:
                        results.append("... (truncated)")
                        return "\n".join(results)
    return "\n".join(results) if results else f"No matches for: {pattern!r}"


def _match_glob(filename: str, pattern: str) -> bool:
    import fnmatch
    return fnmatch.fnmatch(filename, pattern)
