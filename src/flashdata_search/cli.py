"""Command line search and offline replay."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import sys
from importlib.resources import files
from pathlib import Path

from flashdata.errors import APIError, FlashDataError

from .search import SearchClient, SearchResult, collect, export_results, read_queries

CONFIG = """# Keep this local file out of source control.
API_KEY = "your-flashdata-api-key"
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="YouTube Search API: queries to CSV, JSONL and IDs"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create config.py with an API-key placeholder")
    init.add_argument("--config", type=Path, default=Path("config.py"))
    demo = commands.add_parser(
        "demo", help="Replay a recorded public search; no API key or network"
    )
    demo.add_argument("--output", type=Path, default=Path("output/demo"))
    search = commands.add_parser("search", help="Run live searches with your FlashData API key")
    inputs = search.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--query")
    inputs.add_argument("--queries", type=Path, help="UTF-8 text file, one query per line")
    search.add_argument("--output", type=Path, required=True)
    search.add_argument("--config", type=Path, default=Path("config.py"))
    search.add_argument("--limit", type=int, default=20, help="Results per query (default: 20)")
    search.add_argument(
        "--extended", action="store_true", help="Use separately priced Extended Search"
    )
    search.add_argument("--duration", choices=["<4", "4-20", ">20"])
    search.add_argument(
        "--upload-date", choices=["last_hour", "today", "this_week", "this_month", "this_year"]
    )
    search.add_argument("--sort-by", choices=["relevance", "view_count", "upload_date", "rating"])
    search.add_argument(
        "--subtitles", action="store_true", help="Require YouTube's subtitles filter"
    )
    search.add_argument("--resume", action="store_true", help="Reuse saved completed responses")
    search.add_argument("--interval", type=float, default=1, help="Seconds between queries")
    search.add_argument("--retries", type=int, default=2, help="429-only retries, 0–3")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            with args.config.open("x", encoding="utf-8") as handle:
                handle.write(CONFIG)
            print(f"Created {args.config}. Put your API key directly in this Python file.")
            return 0
        if args.command == "demo":
            saved = json.loads(
                files("flashdata_search")
                .joinpath("recorded/search.json")
                .read_text(encoding="utf-8")
            )
            result = SearchResult(
                saved["query"], "youtube_search", saved["response"], saved["retrieved_at"]
            )
            summary = export_results([result], args.output)
            print(f"Offline replay: {saved['provenance']}")
        else:
            key = runpy.run_path(str(args.config)).get("API_KEY") if args.config.exists() else None
            key = key or os.environ.get("FLASHDATA_API_KEY")
            if not isinstance(key, str) or not key.strip() or key == "your-flashdata-api-key":
                raise ValueError("Run flashdata-search init, then set API_KEY in config.py.")
            queries = read_queries(args.queries) if args.queries else [args.query]
            filters = {
                name: getattr(args, name)
                for name in ("duration", "upload_date", "sort_by")
                if getattr(args, name)
            }
            if args.subtitles:
                filters["subtitles"] = True
            with SearchClient(api_key=key, retries=args.retries) as client:
                summary = collect(
                    client,
                    queries,
                    args.output,
                    max_results=args.limit,
                    extended=args.extended,
                    filters=filters,
                    resume=args.resume,
                    interval=args.interval,
                )
        print(f"{summary['completed_queries']} queries; {summary['unique_videos']} unique videos")
        print(f"Saved videos.csv, videos.jsonl, video-ids.txt and summary.json in {args.output}")
        return 0
    except APIError as exc:
        print(
            f"FlashData HTTP {exc.status_code}. See docs/troubleshooting.md and console History.",
            file=sys.stderr,
        )
    except FlashDataError as exc:
        print(
            f"{type(exc).__name__}: check console History before submitting again.", file=sys.stderr
        )
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
    return 1
