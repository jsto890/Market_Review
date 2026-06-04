from datetime import date, timedelta

from stock_chatter.backtest import backtest_accounts


def test_backtest_ranks_realized_account_returns_above_noisy_calls():
    signals = [
        _signal("WIN1", "@aleabitoreddit", "core_alpha", "1.00", "entry", "0.00"),
        _signal("WIN2", "@aleabitoreddit", "core_alpha", "1.00", "entry", "0.00"),
        _signal("LOSE1", "@Gubloinvestor", "sentiment_noise", "0.35", "entry", "0.60"),
        _signal("LOSE2", "@Gubloinvestor", "sentiment_noise", "0.35", "entry", "0.60"),
    ]
    prices = (
        _price_rows("WIN1", start_open=10, day_20_close=13)
        + _price_rows("WIN2", start_open=20, day_20_close=25)
        + _price_rows("LOSE1", start_open=10, day_20_close=8)
        + _price_rows("LOSE2", start_open=20, day_20_close=16)
    )
    rows = backtest_accounts(signals, prices)
    assert rows[0]["account"] == "@aleabitoreddit"
    assert float(rows[0]["avg_ret_20d"]) > 0
    assert float(rows[1]["avg_ret_20d"]) < 0


def test_backtest_stays_pending_without_5d_or_20d_evidence():
    signals = [_signal("FAST", "@aleabitoreddit", "core_alpha", "1.00", "entry", "0.00")]
    prices = _price_rows("FAST", start_open=10, day_20_close=12)[:3]
    rows = backtest_accounts(signals, prices)
    assert rows[0]["complete_1d_count"] == "1"
    assert rows[0]["complete_5d_count"] == "0"
    assert rows[0]["complete_20d_count"] == "0"
    assert rows[0]["trust_label"] == "pending_forward_data"
    assert rows[0]["evidence_status"] == "1d_only"


def test_backtest_excludes_mentions_from_actionable_returns():
    signals = [
        _signal("FAST", "@aleabitoreddit", "core_alpha", "1.00", "mention", "0.00"),
        _signal("FAST", "@aleabitoreddit", "core_alpha", "1.00", "entry", "0.00"),
    ]
    rows = backtest_accounts(signals, _price_rows("FAST", start_open=10, day_20_close=12))
    assert rows[0]["signal_count"] == "2"
    assert rows[0]["mention_count"] == "1"
    assert rows[0]["actionable_count"] == "1"


def _signal(ticker, account, tier, weight, action, hype):
    return {
        "ticker": ticker,
        "account": account,
        "account_tier": tier,
        "account_weight": weight,
        "action": action,
        "direction": "long",
        "hype_score": hype,
        "tweet_created_at": "2026-04-01T12:00:00Z",
    }


def _price_rows(ticker, *, start_open, day_20_close):
    start = date(2026, 4, 1)
    rows = []
    for idx in range(25):
        progress = idx / 20 if idx <= 20 else 1
        close = start_open + (day_20_close - start_open) * progress
        rows.append(
            {
                "ticker": ticker,
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": f"{start_open:.6f}" if idx == 0 else f"{close:.6f}",
                "high": f"{max(start_open, close) * 1.02:.6f}",
                "low": f"{min(start_open, close) * 0.98:.6f}",
                "close": f"{close:.6f}",
                "volume": "1000000",
            }
        )
    return rows
