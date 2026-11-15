"""Check public writeup routes and packaged evidence, without a model or Modal call."""
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from modal_writeup import _web_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    with TestClient(_web_app(ROOT / "docs/writeup.html")) as client:
        yield client


def test_page_and_evidence_are_packaged(client):
    page = client.get("/")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-cache"
    assert '<h1 id="title">RoyaleBench</h1>' in page.text
    assert client.get("/writeup.html").content == page.content
    snapshot = client.get("/writeup-assets/results.json")
    assert snapshot.status_code == 200
    assert snapshot.headers["content-type"].startswith("application/json")
    data = snapshot.json()
    assert data["dataset"] == "royalebench/royalebench-v9@1"
    assert len(data["models"]) == 12
    assert sum(m["attempts"] for m in data["models"]) == 252


@pytest.mark.parametrize("name", ["opus", "reference"])
def test_replay_and_range_request(client, name):
    url = f"/writeup-assets/{name}-replay.html"
    replay = client.get(url)
    assert replay.status_code == 200
    assert 'id="replay-data"' in replay.text
    assert "royalebench-seek" in replay.text
    partial = client.get(url, headers={"Range": "bytes=0-99"})
    assert partial.status_code == 206
    assert partial.content == replay.content[:100]


@pytest.mark.parametrize("name", ["tactics_clips.md", "royalebench_v9_failure_analysis.md"])
def test_only_linked_guides_redirect(client, name):
    guide = client.get(f"/{name}", follow_redirects=False)
    assert guide.status_code == 307
    assert guide.headers["location"] == f"https://github.com/ishanvepa/RoyaleBench/blob/main/docs/{name}"
    assert client.get("/not-a-guide.md", follow_redirects=False).status_code == 404


@pytest.mark.parametrize("url", ["/.env", "/writeup-assets/.env", "/writeup-assets/%2e%2e/.env", "/writeup-assets/missing.json", "/writeup.md", "/royalebench_v9.md", "/royalebench_v4.md"])
def test_private_and_missing_files_are_not_served(client, url):
    assert client.get(url).status_code == 404
