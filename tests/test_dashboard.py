from stock_chatter.dashboard import render_dashboard


def test_dashboard_contains_core_ui_and_embedded_data():
    html = render_dashboard(
        setups=[
            {
                "ticker": "ARM",
                "setup_label": "late_chase",
                "quality_score": "5.4",
                "mention_count": "6",
                "distinct_account_count": "3",
                "prior_ret_1d": "0.10",
                "prior_ret_5d": "0.20",
                "relative_volume": "2.5",
                "distance_from_20d_high": "-0.01",
                "reason": "already moved",
                "catalysts": "ai_infrastructure",
                "top_accounts": "@aleabitoreddit",
                "price_data_available": "true",
            }
        ],
        leaderboard=[{"account": "@aleabitoreddit", "leaderboard_score": "10", "mention_count": "1"}],
        watchlist=[{"ticker": "ARM", "status": "crowded"}],
        signals=[
            {
                "account": "@aleabitoreddit",
                "tweet_created_at": "2026-05-07T12:00:00Z",
                "ticker": "ARM",
                "action": "entry",
                "text": "Watching $ARM after earnings",
                "url": "https://x.com/aleabitoreddit/status/1",
            }
        ],
        backtest=[{"account": "@aleabitoreddit", "trust_score": "12", "trust_label": "promising"}],
    )
    assert "Stock Chatter Dashboard" in html
    assert "Fresh Watch" in html
    assert "Already Ran / Chase Risk" in html
    assert "dashboard-data" in html
    assert "ARM" in html
    assert "Follow Feed" in html
    assert "Trust Backtest" in html
