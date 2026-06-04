from stock_chatter.scoring import attach_forward_returns, score_accounts


def test_attach_forward_returns_uses_same_day_open_before_market():
    signals = [
        {
            "account": "@aleabitoreddit",
            "tweet_created_at": "2026-05-07T12:00:00Z",
            "ticker": "ABC",
            "action": "entry",
            "direction": "long",
            "hype_score": "0",
        }
    ]
    prices = [
        {"ticker": "ABC", "date": "2026-05-07", "open": "10", "high": "11", "low": "9", "close": "10.5"},
        {"ticker": "ABC", "date": "2026-05-08", "open": "10.5", "high": "12", "low": "10", "close": "11"},
        {"ticker": "ABC", "date": "2026-05-11", "open": "11", "high": "13", "low": "10", "close": "12"},
        {"ticker": "ABC", "date": "2026-05-12", "open": "12", "high": "14", "low": "11", "close": "13"},
        {"ticker": "ABC", "date": "2026-05-13", "open": "13", "high": "15", "low": "12", "close": "14"},
        {"ticker": "ABC", "date": "2026-05-14", "open": "14", "high": "16", "low": "13", "close": "15"},
    ]
    scored = attach_forward_returns(signals, prices)
    assert scored[0]["entry_date"] == "2026-05-07"
    assert scored[0]["ret_1d"] == "0.100000"
    assert scored[0]["ret_5d"] == "0.500000"


def test_score_accounts_marks_pending_without_completed_20d_returns():
    rows = score_accounts(
        [{"account": "@aleabitoreddit", "ticker": "ABC", "action": "entry", "direction": "long", "tweet_created_at": "2026-05-07T12:00:00Z", "hype_score": "0"}],
        [{"ticker": "ABC", "date": "2026-05-07", "open": "10", "high": "10", "low": "10", "close": "10"}],
    )
    assert rows[0]["status"] == "pending_returns"
