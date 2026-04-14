"""
Glob tool — finds files by name/path pattern using pathlib.
"""

import os
from pathlib import Path

from langchain_core.tools import tool


def make_glob_tool(repo_path: str):
    """Return a glob tool bound to `repo_path`."""

    @tool
    def glob(
        pattern: str,
        path: str = "",
    ) -> str:
        """
        Find files by name or path pattern. Use this to explore the repository
        structure, locate files of a given type, or check if a specific file exists.

        Returns matching file paths sorted by modification time (newest first).

        Args:
            pattern: Glob pattern to match against file paths.
                     Examples: "**/*.py", "src/**/*.ts", "**/*.{json,yaml}",
                               "**/test_*.py", "*.md"
            path: Sub-directory inside the repo to restrict the search.
                  Leave empty to search the entire repo.
        """
        search_root = Path(repo_path) / path if path else Path(repo_path)

        if not search_root.exists():
            return f"Path does not exist: {search_root}"

        try:
            matches = sorted(
                search_root.rglob(pattern) if "**" in pattern else search_root.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception as exc:
            return f"Glob error: {exc}"

        if not matches:
            return f"No files matched pattern: {pattern!r} under {search_root}"

        repo_root = Path(repo_path)
        paths = [str(p.relative_to(repo_root)) for p in matches]

        if len(paths) > 200:
            paths = paths[:200]
            paths.append(f"... (truncated to 200 of {len(matches)} matches)")

        return "\n".join(paths)

    return glob
