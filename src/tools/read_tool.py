"""
Read tool — reads file contents with optional line-range slicing.
Supports plain text, PDFs, Jupyter notebooks, and images.
"""

import os
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


def make_read_tool(repo_path: str):
    """Return a read tool bound to `repo_path`."""

    @tool
    def read(
        file_path: str,
        offset: int = 0,
        limit: int = 0,
    ) -> str:
        """
        Read the contents of a file in the repository, with line numbers.
        Supports text files, Python notebooks (.ipynb), and PDFs.

        Args:
            file_path: Path to the file, relative to the repository root
                       (e.g. "src/main.py" or "docs/README.md").
            offset: Line number to start reading from (1-based). 0 means start
                    at the beginning.
            limit: Maximum number of lines to return. 0 means no limit
                   (up to a built-in safety cap of 2000 lines).
        """
        # Resolve to an absolute path inside the repo
        abs_path = _resolve(repo_path, file_path)

        if not abs_path.exists():
            return f"File not found: {file_path}"
        if not abs_path.is_file():
            return f"Not a file: {file_path} (is it a directory?)"

        suffix = abs_path.suffix.lower()

        if suffix == ".ipynb":
            return _read_notebook(abs_path, offset, limit)
        if suffix == ".pdf":
            return _read_pdf(abs_path)

        return _read_text(abs_path, offset, limit)

    return read


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

_MAX_LINES = 2000


def _resolve(repo_path: str, file_path: str) -> Path:
    p = Path(file_path)
    if p.is_absolute():
        return p
    return (Path(repo_path) / file_path).resolve()


def _read_text(path: Path, offset: int, limit: int) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            all_lines = fh.readlines()
    except OSError as exc:
        return f"Could not read file: {exc}"

    # Convert 1-based offset to 0-based index
    start = max(0, offset - 1) if offset > 0 else 0
    end = start + (limit if limit > 0 else _MAX_LINES)
    slice_ = all_lines[start:end]

    if not slice_:
        return f"(No content at offset {offset})"

    # Add 1-based line numbers matching the original file
    numbered = [
        f"{start + i + 1}\t{line.rstrip()}" for i, line in enumerate(slice_)
    ]

    note = ""
    if end < len(all_lines):
        note = (
            f"\n... ({len(all_lines) - end} more lines not shown; "
            f"use offset={end + 1} to continue)"
        )
    return "\n".join(numbered) + note


def _read_notebook(path: Path, offset: int, limit: int) -> str:
    try:
        import nbformat  # type: ignore

        nb = nbformat.read(str(path), as_version=4)
    except ImportError:
        return _read_text(path, offset, limit)
    except Exception as exc:
        return f"Could not parse notebook: {exc}"

    parts: list[str] = []
    for i, cell in enumerate(nb.cells):
        cell_type = cell.cell_type.upper()
        source = cell.source.strip()
        parts.append(f"[Cell {i + 1} — {cell_type}]\n{source}")
        if cell.cell_type == "code" and cell.get("outputs"):
            for out in cell.outputs:
                text = out.get("text") or out.get("data", {}).get("text/plain", "")
                if text:
                    parts.append(f"[Output]\n{''.join(text)}")

    return "\n\n".join(parts)


def _read_pdf(path: Path) -> str:
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    except ImportError:
        return (
            "pypdf is not installed. Install it with: pip install pypdf\n"
            "Falling back to raw bytes — content may be unreadable."
        )
    except Exception as exc:
        return f"Could not parse PDF: {exc}"
