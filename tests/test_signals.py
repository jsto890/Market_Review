from stock_chatter.signals import classify_text, extract_signals, extract_tickers


def test_extract_tickers_dedupes_and_ignores_numbers():
    assert extract_tickers("Watching $rklb and $RKLB, not $100 or cash.") == ["RKLB"]


def test_classify_entry_with_catalyst():
    result = classify_text("Bought $MU on HBM memory earnings guide breakout")
    assert result["action"] == "entry"
    assert result["direction"] == "long"
    assert "earnings" in result["catalysts"]
    assert "ai_infrastructure" in result["catalysts"]


def test_extract_signals_adds_account_tier():
    posts = [
        {
            "id": "1",
            "account": "@aleabitoreddit",
            "created_at": "2026-05-07T12:00:00Z",
            "text": "Long $LITE after earnings",
            "url": "https://x.com/aleabitoreddit/status/1",
        }
    ]
    signals = extract_signals(posts)
    assert signals[0]["ticker"] == "LITE"
    assert signals[0]["account_tier"] == "core_alpha"


def test_extract_signals_prefers_x_cashtag_entities():
    posts = [
        {
            "id": "1",
            "account": "@aleabitoreddit",
            "created_at": "2026-05-07T12:00:00Z",
            "text": "Long dollar amount $100 but entity says ticker",
            "entities": {"cashtags": [{"tag": "lite"}]},
            "url": "https://x.com/aleabitoreddit/status/1",
        }
    ]
    signals = extract_signals(posts)
    assert [row["ticker"] for row in signals] == ["LITE"]
