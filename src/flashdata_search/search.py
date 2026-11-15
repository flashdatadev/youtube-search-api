"""A small video-discovery workflow on top of the official FlashData SDK."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from flashdata import FlashData
from flashdata.errors import APIError

ENUM_FILTERS = {
    "type": ("video",),
    "duration": ("<4", "4-20", ">20"),
    "sort_by": ("relevance", "view_count", "upload_date", "rating"),
    "upload_date": ("last_hour", "today", "this_week", "this_month", "this_year"),
}
FEATURES = {
    "360",
    "3d",
    "4k",
    "creative_commons",
    "hd",
    "hdr",
    "live",
    "location",
    "purchased",
    "subtitles",
    "vr180",
}
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_queries(queries: Iterable[str]) -> list[str]:
    if isinstance(queries, str):
        queries = [queries]
    result: list[str] = []
    for query in queries:
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 2000:
            raise ValueError("Each query must contain 1–2,000 characters.")
        query = query.strip()
        if query not in result:
            result.append(query)
    if not result:
        raise ValueError("Provide at least one query.")
    return result


def read_queries(path: str | Path) -> list[str]:
    """Read a UTF-8 file: one query per line; ignore blanks and # comments."""
    return normalize_queries(
        line
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def options(extended: bool, max_results: int, filters: dict | None) -> dict:
    if not isinstance(extended, bool):
        raise ValueError("extended must be a boolean.")
    maximum = 700 if extended else 20
    if type(max_results) is not int or not 1 <= max_results <= maximum:
        raise ValueError(
            f"max_results must be 1–{maximum}; choose extended=True for larger searches."
        )
    if filters is not None and not isinstance(filters, dict):
        raise ValueError("filters must be a dictionary.")
    selected = {"type": "video", **(filters or {})}
    for name, value in selected.items():
        if name in ENUM_FILTERS:
            if value not in ENUM_FILTERS[name]:
                raise ValueError(f"{name} must be one of {ENUM_FILTERS[name]}.")
        elif name not in FEATURES or type(value) is not bool:
            raise ValueError(f"Unsupported filter or value: {name}.")
    return {
        "source": "youtube_search_extended" if extended else "youtube_search",
        "max_results": max_results,
        "filters": selected,
    }


@dataclass
class SearchResult:
    query: str
    source: str
    raw: dict[str, Any]
    retrieved_at: str

    @property
    def videos(self) -> list[dict[str, Any]]:
        result = []
        for position, row in enumerate(self.items, 1):
            video_id = row.get("videoId")
            if isinstance(video_id, str) and VIDEO_ID.fullmatch(video_id):
                result.append(
                    {
                        **row,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "position": position,
                    }
                )
        return result

    @property
    def items(self) -> list[dict[str, Any]]:
        raw = self.raw
        if not isinstance(raw, dict) or raw.get("status") != "done":
            raise ValueError("Expected a completed search response (status: done).")
        if raw.get("source") != self.source:
            raise ValueError("Response source does not match the requested search source.")
        pages = raw.get("results")
        if not isinstance(pages, list) or not pages:
            raise ValueError("Expected results[].results in the search response.")
        items = []
        for page in pages:
            if not isinstance(page, dict) or not isinstance(page.get("results"), list):
                raise ValueError("Expected results[].results in the search response.")
            if page.get("query", self.query) != self.query:
                raise ValueError("Response query does not match the requested query.")
            if any(not isinstance(row, dict) for row in page["results"]):
                raise ValueError("Expected search result objects.")
            items.extend(page["results"])
        return items


def retry_delay(value: str | None, attempt: int) -> float:
    if value:
        try:
            delay = float(value)
        except ValueError:
            try:
                moment = parsedate_to_datetime(value)
                if moment.tzinfo is None:
                    moment = moment.replace(tzinfo=timezone.utc)
                delay = (moment - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                delay = 2**attempt
    else:
        delay = 2**attempt
    if not math.isfinite(delay):
        return 61
    return max(0, delay)


class SearchClient:
    """Managed YouTube video search. Only explicit HTTP 429 responses are retried."""

    def __init__(self, api_key: str, *, retries: int = 2, timeout: float = 120):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Provide your FlashData API key.")
        if type(retries) is not int or not 0 <= retries <= 3:
            raise ValueError("retries must be 0–3.")
        self._sdk = FlashData(api_key=api_key, timeout=timeout)
        self.retries = retries

    def __enter__(self) -> SearchClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def close(self) -> None:
        self._sdk.close()

    def search(
        self,
        query: str,
        *,
        max_results: int = 20,
        extended: bool = False,
        filters: dict | None = None,
    ) -> SearchResult:
        query = normalize_queries([query])[0]
        config = options(extended, max_results, filters)
        method = self._sdk.youtube.search_extended if extended else self._sdk.youtube.search
        for attempt in range(self.retries + 1):
            try:
                raw = method(query, max_results=max_results, filters=config["filters"])
                result = SearchResult(query, config["source"], raw, timestamp())
                _ = result.items  # Validate before treating the response as a successful query.
                return result
            except APIError as exc:
                delay = retry_delay(exc.retry_after, attempt)
                if exc.status_code != 429 or attempt == self.retries or delay > 60:
                    raise
                time.sleep(delay)
        raise AssertionError("Unreachable retry state")


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="")
    os.replace(temporary, path)


def save_json(path: Path, data: Any) -> None:
    atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def csv_value(value: Any) -> Any:
    # Titles and query strings are untrusted spreadsheet input.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def export_results(results: Iterable[SearchResult], output: str | Path) -> dict:
    """Write a merged video list; preserve every query match and its source position."""
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=True)
    videos: dict[str, dict] = {}
    searches = []
    for result in results:
        rows = result.videos
        for row in rows:
            video_id = row["videoId"]
            match = {
                "query": result.query,
                "position": row["position"],
                "source": result.source,
                "retrieved_at": result.retrieved_at,
            }
            if video_id not in videos:
                videos[video_id] = {**row, "matches": []}
            if match not in videos[video_id]["matches"]:
                videos[video_id]["matches"].append(match)
        searches.append(
            {
                "query": result.query,
                "source": result.source,
                "retrieved_at": result.retrieved_at,
                "returned_items": len(result.items),
                "video_items": len(rows),
                "skipped_items": len(result.items) - len(rows),
                "usage": result.raw.get("usage"),
            }
        )
    atomic_text(
        folder / "videos.jsonl",
        "".join(json.dumps(v, ensure_ascii=False) + "\n" for v in videos.values()),
    )
    atomic_text(folder / "video-ids.txt", "".join(key + "\n" for key in videos))
    columns = ["videoId", "title", "url", "channel", "duration", "viewCount", "queries", "matches"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for video in videos.values():
        row = {key: video.get(key) for key in columns}
        row["queries"] = " | ".join(dict.fromkeys(m["query"] for m in video["matches"]))
        row["matches"] = json.dumps(video["matches"], ensure_ascii=False)
        writer.writerow({key: csv_value(value) for key, value in row.items()})
    atomic_text(folder / "videos.csv", stream.getvalue())
    summary = {
        "unique_videos": len(videos),
        "completed_queries": len(searches),
        "searches": searches,
    }
    save_json(folder / "summary.json", summary)
    return summary


def collect(
    client: SearchClient,
    queries: Iterable[str],
    output: str | Path,
    *,
    max_results: int = 20,
    extended: bool = False,
    filters: dict | None = None,
    resume: bool = False,
    interval: float = 1,
) -> dict:
    """Collect sequential searches, checkpoint completed responses, then export unique videos."""
    names = normalize_queries(queries)
    config = {**options(extended, max_results, filters), "queries": names}
    if not isinstance(interval, (int, float)) or not math.isfinite(interval) or interval < 0:
        raise ValueError("interval must be a finite nonnegative number of seconds.")
    folder = Path(output)
    state_path = folder / "run.json"
    if resume:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("config") != config:
            raise ValueError("Resume requires the same queries, source, filters and result limit.")
    else:
        folder.mkdir(parents=True, exist_ok=True)
        if any(folder.iterdir()):
            raise ValueError("Output folder must be empty. Use resume=True for an existing run.")
        state = {
            "version": 1,
            "config": config,
            "started_at": timestamp(),
            "queries": {},
            "complete": False,
        }
        save_json(state_path, state)
    (folder / "responses").mkdir(exist_ok=True)
    results: list[SearchResult] = []
    for index, query in enumerate(names):
        key = str(index)
        response_path = folder / "responses" / f"{index + 1:04d}.json"
        previous = state["queries"].get(key, {})
        if response_path.exists():
            saved = json.loads(response_path.read_text(encoding="utf-8"))
            result = SearchResult(query, config["source"], saved["response"], saved["retrieved_at"])
            _ = result.items
        else:
            if previous.get("status") == "uncertain":
                raise RuntimeError(
                    "Previous request outcome is unknown. Check console History; "
                    "use a new output folder if you decide to submit again."
                )
            state["queries"][key] = {"status": "uncertain"}
            save_json(state_path, state)
            try:
                result = client.search(
                    query, max_results=max_results, extended=extended, filters=config["filters"]
                )
                save_json(
                    response_path, {"retrieved_at": result.retrieved_at, "response": result.raw}
                )
            except Exception as exc:
                if isinstance(exc, APIError) and 400 <= exc.status_code < 500:
                    state["queries"][key] = {"status": "rejected", "http_status": exc.status_code}
                    save_json(state_path, state)
                export_results(results, folder)
                raise
            if index + 1 < len(names):
                time.sleep(interval)
        results.append(result)
        state["queries"][key] = {"status": "done", "response": f"responses/{index + 1:04d}.json"}
        save_json(state_path, state)
    summary = export_results(results, folder)
    state["complete"] = True
    save_json(state_path, state)
    return summary
