"""
Symbol Extractor tool — extracts function, class, and method names with
their start/end line numbers from source files.

Primary implementation: tree-sitter (>=0.24, new API) with individual
language packages (tree-sitter-python, tree-sitter-javascript, etc.).
Fallback: regex-based heuristic for common languages.
"""

import os
import re
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

# Language extension → tree-sitter language key
_EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c",
    ".rb": "ruby",
    ".cs": "c_sharp",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
}

# tree-sitter node types that represent named symbols
_SYMBOL_NODE_TYPES = {
    "python": ["function_definition", "class_definition", "decorated_definition"],
    "javascript": ["function_declaration", "class_declaration", "method_definition",
                   "arrow_function", "function_expression"],
    "typescript": ["function_declaration", "class_declaration", "method_definition",
                   "arrow_function", "function_expression"],
    "tsx": ["function_declaration", "class_declaration", "method_definition"],
    "rust": ["function_item", "impl_item", "struct_item", "enum_item", "trait_item"],
    "go": ["function_declaration", "method_declaration", "type_declaration"],
    "java": ["class_declaration", "method_declaration", "constructor_declaration"],
    "cpp": ["function_definition", "class_specifier"],
    "c": ["function_definition"],
    "ruby": ["method", "class", "module"],
    "c_sharp": ["class_declaration", "method_declaration", "constructor_declaration"],
}


def make_symbol_extractor_tool(repo_path: str):
    """Return a symbol extractor tool bound to `repo_path`."""

    @tool
    def extract_symbols(file_path: str) -> str:
        """
        Extract all functions, classes, and methods from a source file with
        their start and end line numbers. Use this BEFORE reading a large file —
        it tells you exactly which lines a symbol spans so you can read it
        precisely with the read tool.

        Returns a table of: symbol_name | type | start_line | end_line

        Args:
            file_path: Path to the source file, relative to the repository root
                       (e.g. "src/processor.py").
        """
        abs_path = _resolve(repo_path, file_path)

        if not abs_path.exists():
            return f"File not found: {file_path}"
        if not abs_path.is_file():
            return f"Not a file: {file_path}"

        lang = _EXT_TO_LANG.get(abs_path.suffix.lower())
        if not lang:
            return (
                f"Unsupported file type: {abs_path.suffix!r}. "
                f"Supported: {', '.join(sorted(_EXT_TO_LANG.keys()))}"
            )

        source = abs_path.read_bytes()

        # Try tree-sitter first
        symbols = _extract_tree_sitter(source, lang)
        if symbols is None:
            # Fall back to regex
            symbols = _extract_regex(source.decode("utf-8", errors="replace"), lang)

        if not symbols:
            return f"No symbols found in {file_path}"

        # Format as a table
        header = f"{'Symbol':<50} {'Type':<25} {'Start':>6} {'End':>6}"
        separator = "-" * len(header)
        rows = [
            f"{name:<50} {sym_type:<25} {start:>6} {end:>6}"
            for name, sym_type, start, end in symbols
        ]
        return "\n".join([header, separator] + rows)

    return extract_symbols


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolve(repo_path: str, file_path: str) -> Path:
    p = Path(file_path)
    if p.is_absolute():
        return p
    return (Path(repo_path) / file_path).resolve()


def _get_ts_parser(lang: str):
    """Return a tree-sitter Parser for the given language key, or None."""
    try:
        from tree_sitter import Language, Parser  # type: ignore

        if lang == "python":
            import tree_sitter_python as mod  # type: ignore
            language = Language(mod.language())
        elif lang in ("javascript", "jsx"):
            import tree_sitter_javascript as mod  # type: ignore
            language = Language(mod.language())
        elif lang == "typescript":
            import tree_sitter_typescript as mod  # type: ignore
            language = Language(mod.language_typescript())
        elif lang == "tsx":
            import tree_sitter_typescript as mod  # type: ignore
            language = Language(mod.language_tsx())
        elif lang == "rust":
            import tree_sitter_rust as mod  # type: ignore
            language = Language(mod.language())
        elif lang == "go":
            import tree_sitter_go as mod  # type: ignore
            language = Language(mod.language())
        elif lang == "java":
            import tree_sitter_java as mod  # type: ignore
            language = Language(mod.language())
        elif lang == "c":
            import tree_sitter_c as mod  # type: ignore
            language = Language(mod.language())
        elif lang == "cpp":
            import tree_sitter_cpp as mod  # type: ignore
            language = Language(mod.language())
        else:
            return None

        return Parser(language)
    except Exception:
        return None


def _extract_tree_sitter(
    source: bytes, lang: str
) -> Optional[list[tuple[str, str, int, int]]]:
    """Return list of (name, type, start_line, end_line) or None on failure."""
    parser = _get_ts_parser(lang)
    if parser is None:
        return None

    try:
        tree = parser.parse(source)
    except Exception:
        return None

    target_types = set(_SYMBOL_NODE_TYPES.get(lang, []))
    symbols: list[tuple[str, str, int, int]] = []

    def walk(node):
        if node.type in target_types:
            name = _get_node_name(node, source)
            sym_type = _simplify_type(node.type)
            start_line = node.start_point[0] + 1  # convert to 1-based
            end_line = node.end_point[0] + 1
            symbols.append((name, sym_type, start_line, end_line))
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return symbols


def _get_node_name(node, source: bytes) -> str:
    """Extract the identifier name from a tree-sitter node."""
    for child in node.children:
        if child.type == "identifier":
            return source[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
    # For decorated definitions (Python), look one level deeper
    for child in node.children:
        for grandchild in child.children:
            if grandchild.type == "identifier":
                return source[grandchild.start_byte:grandchild.end_byte].decode(
                    "utf-8", errors="replace"
                )
    return "<anonymous>"


def _simplify_type(node_type: str) -> str:
    mapping = {
        "function_definition": "function",
        "function_declaration": "function",
        "function_item": "function",
        "function_declaration": "function",
        "method_definition": "method",
        "method_declaration": "method",
        "arrow_function": "arrow_function",
        "class_definition": "class",
        "class_declaration": "class",
        "class_specifier": "class",
        "impl_item": "impl",
        "struct_item": "struct",
        "enum_item": "enum",
        "trait_item": "trait",
        "type_declaration": "type",
        "decorated_definition": "decorated",
        "constructor_declaration": "constructor",
    }
    return mapping.get(node_type, node_type)


# --- Regex fallback -----------------------------------------------------------

_REGEX_PATTERNS = {
    "python": [
        (r"^(?:async\s+)?def\s+(\w+)\s*\(", "function"),
        (r"^class\s+(\w+)", "class"),
    ],
    "javascript": [
        (r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(", "function"),
        (r"^(?:export\s+)?class\s+(\w+)", "class"),
        (r"^\s+(?:async\s+)?(\w+)\s*\(.*\)\s*\{", "method"),
    ],
    "typescript": [
        (r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(", "function"),
        (r"^(?:export\s+)?class\s+(\w+)", "class"),
        (r"^\s+(?:async\s+)?(\w+)\s*\(.*\)\s*[:{]", "method"),
    ],
    "go": [
        (r"^func\s+(?:\(.*?\)\s+)?(\w+)\s*\(", "function"),
        (r"^type\s+(\w+)\s+struct", "struct"),
    ],
    "rust": [
        (r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[\(<]", "function"),
        (r"^(?:pub\s+)?struct\s+(\w+)", "struct"),
        (r"^(?:pub\s+)?enum\s+(\w+)", "enum"),
        (r"^(?:pub\s+)?trait\s+(\w+)", "trait"),
        (r"^impl\s+(?:.*?for\s+)?(\w+)", "impl"),
    ],
    "java": [
        (r"^\s+(?:public|private|protected|static|\s)+\s+\w+\s+(\w+)\s*\(", "method"),
        (r"^(?:public\s+)?(?:abstract\s+)?class\s+(\w+)", "class"),
    ],
}


def _extract_regex(
    source: str, lang: str
) -> list[tuple[str, str, int, int]]:
    patterns = _REGEX_PATTERNS.get(lang, _REGEX_PATTERNS.get("python", []))
    lines = source.splitlines()
    symbols: list[tuple[str, str, int, int]] = []

    for i, line in enumerate(lines):
        for pattern, sym_type in patterns:
            m = re.match(pattern, line, re.IGNORECASE)
            if m:
                name = m.group(1)
                # Estimate end line by scanning for the next top-level definition
                end = _estimate_end(lines, i, sym_type)
                symbols.append((name, sym_type, i + 1, end))
                break

    return symbols


def _estimate_end(lines: list[str], start: int, sym_type: str) -> int:
    """Rough end-line estimator: look for the next non-indented definition."""
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line and not line[0].isspace() and line[0] not in ("#", "@", "/", "*"):
            return i  # next top-level line
    return len(lines)
