"""
Command-line / REPL front end (presentation only).

Reads a query, calls ``QueryEngine.search`` and prints the ranked results.
It contains no ranking, cache, Rocchio or MMR logic.

    python3 -m wl3.cli.main                       # interactive REPL, demo corpus
    python3 -m wl3.cli.main -q "neuron training"  # one-shot query
    python3 -m wl3.cli.main --corpus data/corpus.json --mode tfidf -k 5 --mmr

REPL commands:
    :mode tfidf|bm25|vector   change ranking strategy
    :k N                      change number of results
    :mmr on|off               toggle diversification
    :rel N                    mark result N of the last search relevant
    :reset                    forget this session's feedback
    :stats                    cache / index statistics
    :help, :quit
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

from wl3.engine.factory import DEFAULT_CACHE_DB, build_engine
from wl3.engine.models import RankedResult
from wl3.engine.query_engine import QueryEngine, parse_ranking_mode
from wl3.engine.text import highlight, tokenize_query
from wl3.integration.worklet2_adapter import Worklet2Error

HELP = __doc__.split("REPL commands:")[1].strip("\n")


def format_results(results: list[RankedResult], query: str, color: bool = True) -> str:
    """Render ranked results as text (highlighting query terms)."""
    notice = getattr(results, "notice", "")
    if not results:
        return notice or "No results."
    terms = tokenize_query(query)
    on, off = ("\033[1;33m", "\033[0m") if color else ("", "")
    lines = []
    for r in results:
        snippet = highlight(r.snippet, terms, on, off) if color else r.snippet
        lines.append(f"{r.rank}. {r.title or '(untitled)'}")
        lines.append(f"   URL: {r.url}")
        lines.append(f"   Score: {r.score:.4f}")
        if snippet:
            lines.append(f"   {snippet}")
        lines.append("")
    body = "\n".join(lines).rstrip()
    return f"{notice}\n\n{body}" if notice else body


def run_repl(engine: QueryEngine, mode: str, k: int, use_mmr: bool, color: bool) -> None:
    session_id = str(uuid.uuid4())
    last_results: list[RankedResult] = []
    print("Mini Search Engine — type a query, or :help")
    while True:
        try:
            line = input("Search> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue

        if line.startswith(":"):
            cmd, _, arg = line[1:].partition(" ")
            arg = arg.strip()
            if cmd in ("quit", "q", "exit"):
                return
            elif cmd == "help":
                print(HELP)
            elif cmd == "mode":
                try:
                    mode = parse_ranking_mode(arg).value
                    print(f"ranking mode: {mode}")
                except ValueError as exc:
                    print(exc)
            elif cmd == "k":
                if arg.isdigit() and int(arg) > 0:
                    k = int(arg)
                    print(f"k = {k}")
                else:
                    print("usage: :k <positive integer>")
            elif cmd == "mmr":
                if arg in ("on", "off"):
                    use_mmr = arg == "on"
                    print(f"MMR {'on' if use_mmr else 'off'}")
                else:
                    print("usage: :mmr on|off")
            elif cmd == "rel":
                if arg.isdigit() and 1 <= int(arg) <= len(last_results):
                    doc = last_results[int(arg) - 1]
                    ok = engine.mark_relevant(session_id, doc.doc_id)
                    print("Feedback recorded — next searches are personalised." if ok
                          else "Could not use that document for feedback.")
                else:
                    print("usage: :rel <result number from the last search>")
            elif cmd == "reset":
                engine.reset_feedback(session_id)
                print("Feedback cleared.")
            elif cmd == "stats":
                print(engine.stats())
            else:
                print(f"Unknown command ':{cmd}'. Try :help")
            continue

        try:
            last_results = engine.search(line, session_id, mode, k, use_mmr)
        except Worklet2Error as exc:
            print(f"Search backend error: {exc}")
            continue
        print(format_results(last_results, line, color))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mini Search Engine — Worklet 3 CLI")
    parser.add_argument("-q", "--query", help="run one query and exit")
    parser.add_argument("--mode", default="bm25", help="tfidf | bm25 | vector (default bm25)")
    parser.add_argument("-k", type=int, default=10, help="number of results (default 10)")
    parser.add_argument("--mmr", action="store_true", help="diversify results with MMR")
    parser.add_argument("--backend", help="real Worklet 2 backend, 'module[:attr]'")
    parser.add_argument("--corpus", help="JSON corpus served by the in-memory Worklet 2")
    parser.add_argument("--db", default=DEFAULT_CACHE_DB, help="SQLite cache file")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args(argv)

    if os.name == "nt":
        os.system("")   # switches on ANSI colour support in the Windows console

    try:
        mode = parse_ranking_mode(args.mode).value
        engine = build_engine(args.backend, args.corpus, cache_db_path=args.db)
    except (ValueError, Worklet2Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    color = sys.stdout.isatty() and not args.no_color
    if args.query:
        try:
            results = engine.search(args.query, None, mode, args.k, args.mmr)
        except Worklet2Error as exc:
            print(f"Search backend error: {exc}", file=sys.stderr)
            return 1
        print(format_results(results, args.query, color))
        return 0

    run_repl(engine, mode, args.k, args.mmr, color)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
