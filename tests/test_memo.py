from stock_chatter.memo import render_memo


def test_memo_marks_x_skipped():
    text = render_memo(signals=[], scores=[], x_skipped=True)
    assert "X API coverage skipped" in text
    assert "Top Talked-About Stocks" in text


def test_memo_renders_setup_actionability_sections():
    text = render_memo(
        signals=[],
        scores=[],
        x_skipped=False,
        setups=[
            _setup("ARM", "fresh_watch"),
            _setup("MU", "momentum_confirmed"),
            _setup("AMD", "late_chase"),
            _setup("DARE", "noise"),
            _setup("LMND", "avoid_wait"),
        ],
        leaderboard=[{"account": "@aleabitoreddit", "leaderboard_score": "4.5", "mention_count": "2", "distinct_ticker_count": "2", "top_tickers": "ARM;MU"}],
    )
    assert "## Fresh Watch" in text
    assert "$ARM" in text
    assert "## Momentum Confirmed" in text
    assert "$MU" in text
    assert "## Already Ran / Chase Risk" in text
    assert "$AMD" in text
    assert "## Speculative / Noise" in text
    assert "$DARE" in text
    assert "## Avoid / Wait" in text
    assert "$LMND" in text
    assert "## Account Leaderboard" in text


def _setup(ticker, label):
    return {
        "ticker": ticker,
        "setup_label": label,
        "quality_score": "3.0",
        "mention_count": "2",
        "distinct_account_count": "1",
        "prior_ret_1d": "0.010000",
        "prior_ret_5d": "0.050000",
        "prior_ret_20d": "",
        "catalysts": "earnings",
        "top_accounts": "@aleabitoreddit",
        "reason": "test reason",
        "news_confirmation": "earnings",
    }
