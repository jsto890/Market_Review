import pytest
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from stock_chatter.x_api import XApiError, XCostApprovalRequired, _get_json, build_recent_search_queries, fetch_recent_cashtag_posts


def test_queries_use_cashtag_filter_and_exclude_retweets():
    queries = build_recent_search_queries(["aleabitoreddit", "ParadisLabs"])
    assert len(queries) == 1
    assert "from:aleabitoreddit" in queries[0]
    assert "has:cashtags" in queries[0]
    assert "-is:retweet" in queries[0]


def test_fetch_requires_cost_approval_before_network_call():
    with pytest.raises(XCostApprovalRequired):
        fetch_recent_cashtag_posts(
            start_time=__import__("datetime").datetime(2026, 5, 7, tzinfo=__import__("datetime").timezone.utc),
            end_time=__import__("datetime").datetime(2026, 5, 8, tzinfo=__import__("datetime").timezone.utc),
            handles=["aleabitoreddit"],
            approve_cost=False,
        )


def test_402_is_reported_as_payment_required():
    error = HTTPError("https://api.x.com", 402, "Payment Required", {}, Mock(read=lambda: b"{}"))
    with patch("stock_chatter.x_api.urlopen", side_effect=error):
        with pytest.raises(XApiError, match="Payment Required"):
            _get_json("https://api.x.com", {}, "token")


def test_400_is_reported_without_traceback():
    error = HTTPError("https://api.x.com", 400, "Bad Request", {}, Mock(read=lambda: b'{"detail":"bad end_time"}'))
    with patch("stock_chatter.x_api.urlopen", side_effect=error):
        with pytest.raises(XApiError, match="HTTP 400"):
            _get_json("https://api.x.com", {}, "token")
