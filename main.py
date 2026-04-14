"""
CLI entry point for the GitHub Repository Q&A Agent.

Usage
-----
# Interactive REPL (uses REPO_PATH from .env or current directory)
python main.py

# Point at a specific repository
python main.py --repo /path/to/your/repo

# Single question (non-interactive)
python main.py --repo /path/to/your/repo --ask "What does the authentication module do?"

# Start the API server
python main.py --serve
python main.py --serve --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GitHub Repository Q&A Agent (ReAct — Sonnet + Haiku)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Path to the repository to query (defaults to REPO_PATH env var or '.').",
    )
    parser.add_argument(
        "--ask",
        default=None,
        help="Ask a single question and exit (non-interactive mode).",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the FastAPI server instead of the interactive REPL.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="API server host.")
    parser.add_argument("--port", type=int, default=8000, help="API server port.")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Interactive REPL
# ---------------------------------------------------------------------------


def run_repl(repo_path: str) -> None:
    from src.graph.react_graph import ask

    print(f"\n GitHub Repository Q&A Agent")
    print(f" Repository: {repo_path}")
    print(" Type your question and press Enter. Type 'exit' or Ctrl-C to quit.\n")

    history: list = []

    while True:
        try:
            question = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not question:
            continue
        if question.lower() in {"exit", "quit", "q"}:
            print("Goodbye.")
            break

        print("\nAgent: (thinking...)\n")
        try:
            answer, history = ask(question, repo_path, history)
            print(f"Agent: {answer}\n")
        except Exception as exc:
            print(f"[Error] {exc}\n")


# ---------------------------------------------------------------------------
# Single-question mode
# ---------------------------------------------------------------------------


def run_single(repo_path: str, question: str) -> None:
    from src.graph.react_graph import ask

    print(f"Repository: {repo_path}")
    print(f"Question:   {question}\n")
    try:
        answer, _ = ask(question, repo_path, [])
        print(f"Answer:\n{answer}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# API server mode
# ---------------------------------------------------------------------------


def run_server(host: str, port: int) -> None:
    import uvicorn

    print(f" Starting API server on http://{host}:{port}")
    print(" Endpoints:")
    print(f"   POST http://{host}:{port}/chat")
    print(f"   POST http://{host}:{port}/chat/stream")
    print(f"   GET  http://{host}:{port}/health\n")
    uvicorn.run("api.main:app", host=host, port=port, reload=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()

    # Resolve repository path
    from src.config import settings

    repo_path = args.repo or settings.repo_path

    if args.serve:
        run_server(args.host, args.port)
    elif args.ask:
        run_single(repo_path, args.ask)
    else:
        run_repl(repo_path)


if __name__ == "__main__":
    main()
