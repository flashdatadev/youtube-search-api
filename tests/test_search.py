import csv
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flashdata.errors import APIError, SubmissionUnknownError

from flashdata_search import SearchClient, SearchResult, collect, export_results, read_queries
from flashdata_search.search import options, retry_delay


def response(query="robotics", source="youtube_search", rows=None):
    return {
        "source": source,
        "status": "done",
        "results": [
            {
                "query": query,
                "results": rows
                if rows is not None
                else [{"videoId": "jNQXAC9IVRw", "title": "Demo"}],
            }
        ],
        "usage": {"credits": 0.01},
    }


def result(query="robotics", rows=None):
    return SearchResult(query, "youtube_search", response(query, rows=rows), "2026-11-16T00:00:00Z")


@pytest.fixture
def client(monkeypatch):
    sdk = Mock()
    sdk.youtube.search.return_value = response()
    monkeypatch.setattr("flashdata_search.search.FlashData", lambda **kwargs: sdk)
    with SearchClient(api_key="test-key") as value:
        yield value


def test_standard_and_extended_use_correct_sdk_method(client):
    assert client.search("robotics").videos[0]["videoId"] == "jNQXAC9IVRw"
    client._sdk.youtube.search.assert_called_once_with(
        "robotics", max_results=20, filters={"type": "video"}
    )
    client._sdk.youtube.search_extended.return_value = response(source="youtube_search_extended")
    assert (
        client.search("robotics", extended=True, max_results=700).source
        == "youtube_search_extended"
    )
    client._sdk.youtube.search_extended.assert_called_once()


@pytest.mark.parametrize(
    "extended,limit", [(False, 21), (True, 701), (False, 0), (True, True), (1, 5)]
)
def test_invalid_limits_before_http(client, extended, limit):
    with pytest.raises(ValueError):
        client.search("robotics", extended=extended, max_results=limit)
    client._sdk.youtube.search.assert_not_called()


@pytest.mark.parametrize(
    "filters", [{"type": "channel"}, {"gl": "us"}, {"subtitles": "yes"}, {"duration": "long"}, []]
)
def test_filters_are_real_supported_video_filters(filters):
    with pytest.raises(ValueError):
        options(False, 5, filters)


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"status": "failed"},
        response(source="youtube_metadata"),
        {**response(), "results": []},
        {**response(), "results": [{"results": [42]}]},
        response(query="wrong"),
    ],
)
def test_invalid_response_is_not_an_empty_success(bad):
    with pytest.raises(ValueError):
        _ = SearchResult("robotics", "youtube_search", bad, "now").videos


def test_empty_response_is_a_success():
    assert result(rows=[]).videos == []


def test_retry_only_429_and_respect_delay(client, monkeypatch):
    sleep = Mock()
    monkeypatch.setattr("flashdata_search.search.time.sleep", sleep)
    client._sdk.youtube.search.side_effect = [APIError(429, "limit", retry_after="3"), response()]
    client.search("robotics")
    sleep.assert_called_once_with(3)


@pytest.mark.parametrize(
    "error",
    [
        APIError(500, "server"),
        APIError(401, "key"),
        APIError(429, "wait", retry_after="600"),
        SubmissionUnknownError("lost"),
    ],
)
def test_other_errors_never_repeat_submission(client, error):
    client._sdk.youtube.search.side_effect = error
    with pytest.raises(type(error)):
        client.search("robotics")
    assert client._sdk.youtube.search.call_count == 1


def test_retries_are_bounded(client, monkeypatch):
    monkeypatch.setattr("flashdata_search.search.time.sleep", lambda _: None)
    client._sdk.youtube.search.side_effect = APIError(429, "limit", retry_after="0")
    with pytest.raises(APIError):
        client.search("robotics")
    assert client._sdk.youtube.search.call_count == 3


def test_retry_delay_formats():
    assert retry_delay("nonsense", 2) == 4
    assert retry_delay("Wed, 21 Oct 2015 07:28:00 GMT", 0) == 0
    assert retry_delay("NaN", 0) > 60


def test_export_deduplicates_preserving_matches_and_nulls(tmp_path):
    results = [
        result(
            rows=[
                {"videoId": "jNQXAC9IVRw", "title": "First", "viewCount": None},
                {"channelId": "not-a-video"},
            ]
        ),
        result("another query", [{"videoId": "jNQXAC9IVRw", "title": "Newer"}]),
    ]
    summary = export_results(results, tmp_path)
    assert summary["unique_videos"] == 1
    assert summary["searches"][0]["skipped_items"] == 1
    row = json.loads((tmp_path / "videos.jsonl").read_text())
    assert [m["query"] for m in row["matches"]] == ["robotics", "another query"]
    assert row["viewCount"] is None
    assert row["title"] == "First"
    assert (tmp_path / "video-ids.txt").read_text() == "jNQXAC9IVRw\n"


def test_csv_escapes_formulas_and_handles_unicode(tmp_path):
    export_results(
        [
            result(
                "=HYPERLINK(1)",
                [{"videoId": "jNQXAC9IVRw", "title": "=1+1", "channel": "研究频道"}],
            )
        ],
        tmp_path,
    )
    with (tmp_path / "videos.csv").open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["title"] == "'=1+1"
    assert row["queries"].startswith("'")
    assert row["channel"] == "研究频道"


def test_collect_resume_uses_completed_response_without_http(tmp_path):
    client = SimpleNamespace(search=Mock(side_effect=lambda q, **_: result(q)))
    summary = collect(client, ["robotics", "robotics", "battery"], tmp_path, interval=0)
    assert summary["completed_queries"] == 2
    assert client.search.call_count == 2
    client.search.reset_mock()
    assert collect(client, ["robotics", "battery"], tmp_path, resume=True)["unique_videos"] == 1
    client.search.assert_not_called()
    assert json.loads((tmp_path / "run.json").read_text())["complete"]
    assert "api_key" not in (tmp_path / "run.json").read_text()


def test_resume_rejects_changed_config(tmp_path):
    client = SimpleNamespace(search=Mock(return_value=result()))
    collect(client, ["robotics"], tmp_path)
    with pytest.raises(ValueError, match="same queries"):
        collect(client, ["robotics"], tmp_path, max_results=10, resume=True)


def test_incomplete_request_blocks_automatic_resubmission(tmp_path):
    client = SimpleNamespace(search=Mock(side_effect=SubmissionUnknownError("lost")))
    with pytest.raises(SubmissionUnknownError):
        collect(client, ["robotics"], tmp_path)
    client.search.reset_mock()
    with pytest.raises(RuntimeError, match="unknown"):
        collect(client, ["robotics"], tmp_path, resume=True)
    client.search.assert_not_called()


def test_partial_run_keeps_completed_rows_and_can_resume_rejection(tmp_path):
    client = SimpleNamespace(search=Mock(side_effect=[result(), APIError(402, "balance")]))
    with pytest.raises(APIError):
        collect(client, ["robotics", "battery"], tmp_path, interval=0)
    assert json.loads((tmp_path / "summary.json").read_text())["completed_queries"] == 1
    client.search = Mock(return_value=result("battery"))
    assert collect(client, ["robotics", "battery"], tmp_path, resume=True)["completed_queries"] == 2
    client.search.assert_called_once()


def test_read_queries_bom_comments_blanks_duplicates(tmp_path):
    path = tmp_path / "queries.txt"
    path.write_text("\ufeff# topic\n robot \n\nrobot\n电池\n", encoding="utf-8")
    assert read_queries(path) == ["robot", "电池"]


def test_validate_all_queries_before_any_requests(tmp_path):
    client = SimpleNamespace(search=Mock())
    with pytest.raises(ValueError):
        collect(client, ["robotics", " "], tmp_path)
    client.search.assert_not_called()
