import json
from importlib.resources import files
from unittest.mock import Mock

import httpx
import pytest
from flashdata import FlashData

from flashdata_search import SearchClient
from flashdata_search.cli import main


@pytest.mark.parametrize("extended,limit", [(False, 5), (True, 100)])
def test_installed_sdk_sends_expected_authenticated_request(monkeypatch, extended, limit):
    def handle(request):
        assert request.method == "POST"
        assert str(request.url) == "https://data.flashdata.dev/v1/queries/realtime"
        assert request.headers["X-API-Key"] == "fixture-api-key"
        body = json.loads(request.content)
        assert body == {
            "source": "youtube_search_extended" if extended else "youtube_search",
            "query": "battery recycling process",
            "params": {"max_results": limit, "filters": {"type": "video", "subtitles": True}},
        }
        return httpx.Response(
            200,
            json={
                "source": body["source"],
                "status": "done",
                "results": [{"results": [{"videoId": "jNQXAC9IVRw", "title": "Fixture"}]}],
            },
        )

    def sdk(**kwargs):
        return FlashData(**kwargs, transport=httpx.MockTransport(handle), trust_env=False)

    monkeypatch.setattr("flashdata_search.search.FlashData", sdk)
    with SearchClient(api_key="fixture-api-key") as client:
        result = client.search(
            "battery recycling process",
            extended=extended,
            max_results=limit,
            filters={"subtitles": True},
        )
    assert result.videos[0]["url"] == "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def test_cli_replays_all_recorded_results_without_network(tmp_path, monkeypatch, capsys):
    network = Mock(side_effect=AssertionError("Offline demo must not use HTTP"))
    monkeypatch.setattr(httpx.Client, "send", network)
    assert main(["demo", "--output", str(tmp_path)]) == 0
    saved = json.loads(
        files("flashdata_search").joinpath("recorded/search.json").read_text("utf-8")
    )
    rows = [
        json.loads(line) for line in (tmp_path / "videos.jsonl").read_text("utf-8").splitlines()
    ]
    assert len(rows) == 20
    for actual, recorded in zip(rows, saved["response"]["results"][0]["results"], strict=True):
        assert {key: actual[key] for key in recorded} == recorded
        assert actual["matches"][0]["retrieved_at"] == saved["retrieved_at"]
    assert "Offline replay:" in capsys.readouterr().out
    network.assert_not_called()


def test_cli_init_does_not_replace_existing_key(tmp_path):
    config = tmp_path / "config.py"
    assert main(["init", "--config", str(config)]) == 0
    config.write_text('API_KEY = "local-secret"', encoding="utf-8")
    assert main(["init", "--config", str(config)]) == 1
    assert config.read_text() == 'API_KEY = "local-secret"'


def test_placeholder_key_stops_before_network(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = Mock(side_effect=AssertionError("Placeholder must not reach the SDK"))
    monkeypatch.setattr("flashdata_search.cli.SearchClient", client)
    assert main(["init"]) == 0
    assert main(["search", "--query", "robotics", "--output", "output"]) == 1
    client.assert_not_called()
