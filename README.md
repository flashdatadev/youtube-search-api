# YouTube Search API Toolkit

[![Python search toolkit](https://github.com/flashdatadev/youtube-search-api/actions/workflows/ci.yml/badge.svg)](https://github.com/flashdatadev/youtube-search-api/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Search YouTube videos with Python. Filter results, collect multiple queries, and export deduplicated video metadata to CSV, JSONL and video-ID files.**

Built on the official [FlashData Python SDK](https://github.com/flashdatadev/flashdata-python). FlashData runs the search infrastructure; this toolkit handles query lists, saved results and dataset exports. Use your **FlashData API key** for live requests. A Google Cloud API key is not required.

[Quickstart](#quickstart) · [Recorded demo](#try-a-real-search-recording) · [Filters](#filter-youtube-search-results) · [Multiple queries](#search-multiple-queries-and-export-a-dataset) · [Extended Search](#retrieve-more-results-with-extended-search) · [API reference](https://flashdata.dev/docs/sources/youtube_search?utm_source=github&utm_medium=readme&utm_campaign=youtube-search-api)

## Quickstart

Requires Python 3.10+. Install the released wheel; Git is not required:

```bash
python -m pip install "https://github.com/flashdatadev/youtube-search-api/releases/download/v0.1.0/flashdata_youtube_search_api-0.1.0-py3-none-any.whl"
```

[Get a FlashData API key](https://flashdata.dev/signup?utm_source=github&utm_medium=readme&utm_campaign=youtube-search-api), paste it into Python, and run:

```python
from flashdata_search import SearchClient

with SearchClient(api_key="your-flashdata-api-key") as client:
    result = client.search("battery recycling process", max_results=5)

for video in result.videos:
    print(video["title"], video["url"])
```

Each video includes its ID, title, channel, duration, view count and available search fields. `url` and `position` are added locally. The unmodified API response is available as `result.raw`.

To use just the underlying SDK, install `flashdata` and call `client.youtube.search(...)`. See the [direct SDK example](docs/direct-sdk.md).

## Try a real search recording

```bash
flashdata-search demo
```

This replays a **real response captured from FlashData's public search demo**, without an API key or network requests:

- Query: `battery recycling process`
- Response timestamp: **2026-11-15 18:38:13 UTC**
- **20 video results**, including titles, channels, duration and view counts
- All 20 results retained; the recording keeps six fields per video

Browse the [recorded response](src/flashdata_search/recorded/search.json), [CSV](sample-data/videos.csv), [JSONL](sample-data/videos.jsonl) and [video IDs](sample-data/video-ids.txt).

```text
Offline replay: Captured from the live FlashData public search demo...
1 queries; 20 unique videos
Saved videos.csv, videos.jsonl, video-ids.txt and summary.json in output/demo
```

For a fresh live request, use the Python quickstart or [the public search playground](https://flashdata.dev/products/youtube-data#playground). The recording demonstrates the returned data and export format; its view counts are a historical snapshot.

## Filter YouTube search results

Find captioned explainers between four and twenty minutes:

```python
from flashdata_search import SearchClient, export_results

with SearchClient(api_key="your-flashdata-api-key") as client:
    result = client.search(
        "battery recycling process",
        max_results=20,
        filters={"duration": "4-20", "subtitles": True},
    )

export_results([result], "output/captioned-videos")
```

| Filter | Values | Example use |
| --- | --- | --- |
| `duration` | `<4`, `4-20`, `>20` | Short clips, explainers or long talks |
| `upload_date` | `last_hour`, `today`, `this_week`, `this_month`, `this_year` | Recent topic coverage |
| `sort_by` | `relevance`, `view_count`, `upload_date`, `rating` | Request a supported ordering |
| `subtitles` | `True` | Find videos with captions |
| `4k`, `hd`, `hdr`, `live`, `creative_commons` | `True` | Native YouTube feature filters |

The toolkit requests `type="video"` because its exports are video datasets. The underlying API also documents other result types. Refer to the [current filters](https://flashdata.dev/docs/sources/youtube_search#parameters) for the API contract. A subtitles filter does not choose a caption language; select that later in the Transcript API. A Creative Commons search label is not a separate training license.

## Search multiple queries and export a dataset

```python
from flashdata_search import SearchClient, collect

with SearchClient(api_key="your-flashdata-api-key") as client:
    summary = collect(
        client,
        ["battery recycling process", "lithium battery recycling plant"],
        "output/batteries",
        max_results=20,
        filters={"subtitles": True, "duration": "4-20"},
    )

print(summary["unique_videos"], "unique videos")
```

The collector sends sequential requests, with a one-second interval by default. It validates all queries before starting and removes repeated query strings. The same video found by several searches becomes one record with a `matches` array preserving every query, source position, API source and retrieval time. First-seen video metadata is retained.

```text
output/batteries/
  videos.csv           Spreadsheet-friendly fields and query provenance
  videos.jsonl         One unique video per line; all matching queries retained
  video-ids.txt        One video ID per line for downstream APIs
  summary.json         Completed searches, counts, skipped items and returned usage
  run.json             Request settings and per-query checkpoint state
  responses/0001.json  First completed search response
  responses/0002.json  Second completed search response
```

Resume the same call with `resume=True`. Completed responses are read from disk. Changed queries, filters or limits require a new output folder. After an uncertain submission, the collector stops and asks you to check console History before deciding whether to submit again. See [recovery](docs/troubleshooting.md).

## Retrieve more results with Extended Search

```python
from flashdata_search import SearchClient, export_results

with SearchClient(api_key="your-flashdata-api-key") as client:
    result = client.search("robotics research", extended=True, max_results=100)

export_results([result], "output/robotics")
```

| | Standard Search | Extended Search |
| --- | --- | --- |
| API source | `youtube_search` | `youtube_search_extended` |
| Requested results per query | 1–20 | 1–700 |
| Toolkit default | 20 | 20 |
| Price | Standard YouTube Data rate | Separate Extended Search rate |
| SDK method | `youtube.search()` | `youtube.search_extended()` |

Requested counts are upper bounds. The API accepts `max_results`; it does not expose `page` or a continuation-token input. Do not repeat the same query to simulate pagination. For broader discovery, use distinct topics and deduplicate their returned IDs. Country/language inputs are not part of the documented Search schema; YouTube Suggestions has separate localization controls.

Published Standard Search PAYG pricing is **$0.50 per 1,000 requests** at the time of this release. Eligible verified accounts receive shared trial credits, currently equivalent to up to 4,000 standard requests. Extended Search has its own rate. See [current pricing and volume options](https://flashdata.dev/pricing/youtube-data?utm_source=github&utm_medium=readme&utm_campaign=youtube-search-api).

## Command-line use

```bash
flashdata-search init
```

Edit the generated, gitignored `config.py`:

```python
API_KEY = "your-flashdata-api-key"
```

```bash
flashdata-search search --query "robotics research" --limit 20 --output output/robotics
flashdata-search search --queries queries.txt --subtitles --duration 4-20 --output output/batteries
flashdata-search search --query "robotics research" --extended --limit 100 --output output/robotics-extended
```

For the multi-query command, create `queries.txt` with one query per line:

```text
battery recycling process
lithium battery recycling plant
```

Blank lines and lines starting with `#` are ignored. Add `--resume` with the original settings to continue. `--help` lists all options. As an optional alternative, omit `config.py` and supply `FLASHDATA_API_KEY` from your environment.

## Continue into transcripts or bulk video downloads

Review `videos.csv`, select relevant videos and save their IDs in a separate file before enrichment. The files contain **video IDs**, not download URLs or transcript text.

| Next step | Tool or guide |
| --- | --- |
| Retrieve existing captions and timestamps | [YouTube Transcript API toolkit](https://github.com/flashdatadev/youtube-transcript-api) |
| Add video and channel metadata | [YouTube Data API toolkit](https://github.com/flashdatadev/youtube-data-api) |
| Deliver selected media to your cloud storage | [Bulk video download](https://github.com/flashdatadev/bulk-video-download) |
| Scope a managed collection | [YouTube video datasets](https://flashdata.dev/products/youtube-video-datasets?utm_source=github&utm_medium=readme&utm_campaign=youtube-search-api) |
| Follow a complete Python walkthrough | [YouTube Search API in Python](https://flashdata.dev/docs/guides/youtube-search-recipe) |

Search can run without configuring cloud storage. Downloads require their own destination settings. Transcript, metadata and download calls are separate API operations.

## FlashData and the official YouTube Data API

This is an independent FlashData toolkit, not Google's SDK. FlashData uses its own API key, response schema and usage pricing. Google's official `search.list` endpoint uses Google credentials, its own filters, quota system and page tokens. It also supports operations and filters outside this toolkit's video-discovery workflow. See [Google's search reference](https://developers.google.com/youtube/data/reference/rest/v3/search/list) and [the FlashData request reference](https://flashdata.dev/docs/sources/youtube_search).

## Development

```bash
git clone https://github.com/flashdatadev/youtube-search-api.git
cd youtube-search-api
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m build
```

Tests are offline. CI checks Python 3.10 and 3.13 on Linux, macOS and Windows. For bugs, open an [issue](https://github.com/flashdatadev/youtube-search-api/issues) with a minimal example and sanitized response shape. Never include API keys.
