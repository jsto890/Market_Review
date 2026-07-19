import pytest

from stock_chatter import fallback_sources
from stock_chatter.fallback_sources import (
    FallbackSourceError,
    fetch_fallback_posts,
    fetch_reddit_posts,
    fetch_stocktwits_posts,
)
from stock_chatter.signals import extract_tickers_from_post

STOCKTWITS_PAYLOAD = {
    "messages": [
        {
            "id": 111,
            "body": "$SMR breaking out",
            "created_at": "2026-07-20T01:02:03Z",
            "user": {"username": "trader1"},
            "symbols": [{"symbol": "SMR"}],
            "likes": {"total": 5},
            "conversation": {"replies": 2},
        }
    ]
}

REDDIT_PAYLOAD = {
    "data": {
        "children": [
            {
                "data": {
                    "name": "t3_abc",
                    "title": "SMR looking strong",
                    "selftext": "Loading up on $SMR calls",
                    "author": "redditor1",
                    "created_utc": 1784854923,
                    "score": 42,
                    "num_comments": 7,
                    "permalink": "/r/stocks/comments/abc/smr/",
                }
            }
        ]
    }
}


def test_stocktwits_rows_match_posts_schema(monkeypatch):
    monkeypatch.setattr(fallback_sources, "_get_json", lambda url, params=None: STOCKTWITS_PAYLOAD)
    rows = fetch_stocktwits_posts(["SMR"])
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "st-111"
    assert row["account"] == "@st:trader1"
    assert row["source"] == "stocktwits"
    assert row["public_metrics"]["like_count"] == 5
    assert extract_tickers_from_post(row) == ["SMR"]


def test_reddit_rows_match_posts_schema(monkeypatch):
    monkeypatch.setattr(fallback_sources, "_get_json", lambda url, params=None: REDDIT_PAYLOAD)
    rows = fetch_reddit_posts()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "rd-t3_abc"
    assert row["account"] == "@rd:redditor1"
    assert row["created_at"].endswith("Z")
    assert row["source"] == "reddit"
    assert extract_tickers_from_post(row) == ["SMR"]


def test_fallback_tolerates_single_source_failure(monkeypatch):
    def fake_get(url, params=None):
        if "stocktwits" in url:
            raise FallbackSourceError("stocktwits down")
        return REDDIT_PAYLOAD

    monkeypatch.setattr(fallback_sources, "_get_json", fake_get)
    rows, sources = fetch_fallback_posts(["SMR"])
    assert sources == ["reddit"]
    assert len(rows) == 1


def test_fallback_raises_when_all_sources_fail(monkeypatch):
    def fake_get(url, params=None):
        raise FallbackSourceError("down")

    monkeypatch.setattr(fallback_sources, "_get_json", fake_get)
    with pytest.raises(FallbackSourceError):
        fetch_fallback_posts([])
