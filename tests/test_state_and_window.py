from datetime import datetime, timezone

from stock_chatter.scoring import filter_signals_by_lookback


def test_filter_signals_by_lookback_uses_rolling_window():
    rows = [
        {"tweet_created_at": "2026-05-01T00:00:00Z", "ticker": "AAA"},
        {"tweet_created_at": "2026-01-01T00:00:00Z", "ticker": "BBB"},
    ]
    filtered = filter_signals_by_lookback(
        rows,
        90,
        now=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )
    assert [row["ticker"] for row in filtered] == ["AAA"]
