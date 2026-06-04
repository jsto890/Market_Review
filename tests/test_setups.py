from datetime import date, timedelta

from stock_chatter.setups import (
    build_account_leaderboard,
    classify_ticker_setups,
    update_watchlist_memory,
)


def test_setup_labels_cover_actionability_buckets():
    rows = classify_ticker_setups(
        _signals_for_labels(),
        _price_rows("FRESH", 106, ret_1d=0.01, ret_5d=0.06, high_20=125)
        + _price_rows("BUILD", 110, ret_1d=0.01, ret_5d=0.10, high_20=130)
        + _price_rows("MOMO", 112, ret_1d=0.05, ret_5d=0.12, high_20=140)
        + _price_rows("EXT", 118, ret_1d=0.02, ret_5d=0.18, high_20=145)
        + _price_rows("LATE", 112, ret_1d=0.12, ret_5d=0.20, high_20=145)
        + _price_rows("AVOID", 90, ret_1d=-0.02, ret_5d=-0.10, high_20=120),
    )
    labels = {row["ticker"]: row["setup_label"] for row in rows}
    assert labels["FRESH"] == "fresh_watch"
    assert labels["BUILD"] == "building"
    assert labels["MOMO"] == "momentum_confirmed"
    assert labels["EXT"] == "extended"
    assert labels["LATE"] == "late_chase"
    assert labels["AVOID"] == "avoid_wait"
    assert labels["NOISE"] == "noise"


def test_core_alpha_source_weight_beats_equal_sentiment_mentions():
    rows = classify_ticker_setups(
        [
            _signal("CORE", "@aleabitoreddit", "core_alpha", "1.00", "entry", "earnings"),
            _signal("SENT", "@Gubloinvestor", "sentiment_noise", "0.35", "entry", "earnings"),
        ],
        _price_rows("CORE", 106, ret_1d=0.01, ret_5d=0.06, high_20=125)
        + _price_rows("SENT", 106, ret_1d=0.01, ret_5d=0.06, high_20=125),
    )
    by_ticker = {row["ticker"]: row for row in rows}
    assert float(by_ticker["CORE"]["source_score"]) > float(by_ticker["SENT"]["source_score"])
    assert float(by_ticker["CORE"]["quality_score"]) > float(by_ticker["SENT"]["quality_score"])


def test_watchlist_memory_preserves_first_seen_and_updates_latest():
    existing = [
        {
            "ticker": "ARM",
            "first_seen_at": "2026-05-01T00:00:00Z",
            "first_account": "@aleabitoreddit",
            "first_setup_label": "fresh_watch",
            "catalysts": "earnings",
        }
    ]
    setups = [
        {
            "ticker": "ARM",
            "first_seen_at": "2026-05-07T00:00:00Z",
            "first_account": "@ZaStocks",
            "setup_label": "late_chase",
            "quality_score": "3.5",
            "catalysts": "ai_infrastructure",
            "mention_count": "4",
        }
    ]
    memory = update_watchlist_memory(existing, setups)
    assert len(memory) == 1
    assert memory[0]["first_seen_at"] == "2026-05-01T00:00:00Z"
    assert memory[0]["first_account"] == "@aleabitoreddit"
    assert memory[0]["latest_setup_label"] == "late_chase"
    assert memory[0]["status"] == "crowded"
    assert memory[0]["catalysts"] == "ai_infrastructure;earnings"
    assert memory[0]["label_changed"] == "false"


def test_watchlist_memory_does_not_move_latest_backwards_on_backfill():
    existing = [
        {
            "ticker": "ARM",
            "first_seen_at": "2026-05-05T00:00:00Z",
            "latest_seen_at": "2026-05-07T00:00:00Z",
            "first_account": "@aleabitoreddit",
            "first_setup_label": "fresh_watch",
            "latest_setup_label": "fresh_watch",
        }
    ]
    setups = [
        {
            "ticker": "ARM",
            "first_seen_at": "2026-05-01T00:00:00Z",
            "latest_mention_at": "2026-05-02T00:00:00Z",
            "first_account": "@ZaStocks",
            "setup_label": "late_chase",
            "quality_score": "3.5",
            "catalysts": "ai_infrastructure",
            "mention_count": "4",
        }
    ]
    memory = update_watchlist_memory(existing, setups)
    assert memory[0]["first_seen_at"] == "2026-05-01T00:00:00Z"
    assert memory[0]["first_account"] == "@ZaStocks"
    assert memory[0]["latest_seen_at"] == "2026-05-07T00:00:00Z"
    assert memory[0]["label_changed"] == "true"


def test_setup_marks_unpriced_and_ambiguous_warnings():
    rows = classify_ticker_setups([_signal("DRAM", "@Gubloinvestor", "sentiment_noise", "0.35", "mention", "")], [])
    assert rows[0]["asset_type"] == "ambiguous"
    assert "unpriced" in rows[0]["warnings"]
    assert "asset_ambiguous" in rows[0]["warnings"]
    assert rows[0]["confidence_label"] == "low"


def test_account_leaderboard_rewards_first_mentions():
    signals = [
        _signal("ARM", "@aleabitoreddit", "core_alpha", "1.00", "entry", "earnings", created="2026-05-07T00:00:00Z"),
        _signal("ARM", "@ZaStocks", "swing_watchlist", "0.75", "entry", "earnings", created="2026-05-07T01:00:00Z"),
    ]
    setups = [
        {
            "ticker": "ARM",
            "first_seen_at": "2026-05-07T00:00:00Z",
            "first_account": "@aleabitoreddit",
            "quality_score": "5.0",
        }
    ]
    rows = build_account_leaderboard(signals, setups)
    assert rows[0]["account"] == "@aleabitoreddit"
    assert rows[0]["first_mention_count"] == "1"


def _signals_for_labels():
    return [
        _signal("FRESH", "@aleabitoreddit", "core_alpha", "1.00", "entry", "earnings"),
        _signal("BUILD", "@aleabitoreddit", "core_alpha", "1.00", "mention", ""),
        _signal("BUILD", "@ZaStocks", "swing_watchlist", "0.75", "entry", ""),
        _signal("MOMO", "@ParadisLabs", "core_alpha", "1.00", "entry", "ai_infrastructure"),
        _signal("EXT", "@ParadisLabs", "core_alpha", "1.00", "entry", "ai_infrastructure"),
        _signal("LATE", "@ParadisLabs", "core_alpha", "1.00", "entry", "ai_infrastructure"),
        _signal("AVOID", "@ParadisLabs", "core_alpha", "1.00", "exit", "earnings"),
        _signal("NOISE", "@Gubloinvestor", "sentiment_noise", "0.35", "mention", ""),
    ]


def _signal(ticker, account, tier, weight, action, catalysts, created="2026-05-07T00:00:00Z"):
    return {
        "ticker": ticker,
        "account": account,
        "account_tier": tier,
        "account_weight": weight,
        "action": action,
        "direction": "long" if action == "entry" else "neutral",
        "hype_score": "0.00",
        "catalysts": catalysts,
        "tweet_created_at": created,
    }


def _price_rows(ticker, close, *, ret_1d, ret_5d, high_20):
    start = date(2026, 4, 1)
    close_1d = close / (1 + ret_1d)
    close_5d = close / (1 + ret_5d)
    rows = []
    for idx in range(21):
        if idx == 15:
            value = close_5d
        elif idx == 19:
            value = close_1d
        elif idx == 20:
            value = close
        else:
            value = close_5d
        high = high_20 if idx == 5 else value * 1.01
        rows.append(
            {
                "ticker": ticker,
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": f"{value * 0.99:.6f}",
                "high": f"{high:.6f}",
                "low": f"{value * 0.98:.6f}",
                "close": f"{value:.6f}",
                "volume": "1000000",
            }
        )
    return rows
