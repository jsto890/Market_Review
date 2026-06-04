#!/usr/bin/env python3
"""
On-demand Twitter/X cashtag search for a specific ticker.

Searches $TICKER from the full public timeline (not just monitored accounts),
flags which posters are in the following list, and prints a ranked summary.

Usage:
    python ticker_search.py SMR [--since-hours 48] [--max-results 100]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).parent / "src"))
from stock_chatter.accounts import ACCOUNTS, account_for_handle

TIER_ORDER = {"core_alpha": 0, "swing_watchlist": 1, "long_term_research": 2, "sentiment_noise": 3}
FOLLOWING = {a.handle.lower(): a for a in ACCOUNTS}
RECENT_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"


def _bearer() -> str:
    token = os.environ.get("X_BEARER_TOKEN", "")
    if not token:
        sys.exit("X_BEARER_TOKEN not set — run: source ~/.zprofile")
    return token


def _get_json(url: str, params: dict) -> dict:
    req = Request(
        f"{url}?{urlencode(params)}",
        headers={"Authorization": f"Bearer {_bearer()}", "User-Agent": "stock-chatter/0.1"},
    )
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        sys.exit(f"X API error {e.code}: {body}")


def search_ticker(ticker: str, since_hours: int, max_results: int) -> list[dict]:
    end = datetime.now(timezone.utc) - timedelta(seconds=15)
    start = end - timedelta(hours=since_hours)

    def iso(dt: datetime) -> str:
        return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    query = f"${ticker.upper()} -is:retweet lang:en"
    params = {
        "query": query,
        "start_time": iso(start),
        "end_time": iso(end),
        "max_results": str(min(max_results, 100)),
        "tweet.fields": "author_id,created_at,entities,public_metrics",
        "expansions": "author_id",
        "user.fields": "username,name",
    }
    payload = _get_json(RECENT_SEARCH_URL, params)
    users = {u["id"]: u for u in payload.get("includes", {}).get("users", [])}
    posts = []
    for t in payload.get("data", []):
        user = users.get(t.get("author_id"), {})
        handle = f"@{user.get('username', '?')}"
        account = FOLLOWING.get(handle.lower())
        posts.append({
            "id": t["id"],
            "handle": handle,
            "name": user.get("name", ""),
            "created_at": t.get("created_at", ""),
            "text": t.get("text", ""),
            "likes": t.get("public_metrics", {}).get("like_count", 0),
            "retweets": t.get("public_metrics", {}).get("retweet_count", 0),
            "impressions": t.get("public_metrics", {}).get("impression_count", 0),
            "url": f"https://x.com/{user.get('username','')}/status/{t['id']}",
            "in_following": account is not None,
            "tier": account.tier if account else "public",
            "weight": account.score_weight if account else 0.0,
            "purpose": account.purpose if account else "",
        })
    return posts


def _tier_label(tier: str) -> str:
    return {"core_alpha": "CORE ALPHA", "swing_watchlist": "SWING WATCHLIST",
            "long_term_research": "LONG TERM", "sentiment_noise": "SENTIMENT NOISE",
            "public": "PUBLIC"}.get(tier, tier.upper())


def _fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %H:%M UTC")
    except Exception:
        return iso


def print_report(ticker: str, posts: list[dict], since_hours: int) -> None:
    ticker = ticker.upper()
    following_posts = [p for p in posts if p["in_following"]]
    public_posts = sorted([p for p in posts if not p["in_following"]],
                          key=lambda p: p["likes"], reverse=True)

    print(f"\n{'='*65}")
    print(f"  ${ticker}  —  X search  |  last {since_hours}h  |  {len(posts)} posts found")
    print(f"{'='*65}")

    if not posts:
        print("  No posts found in this window.")
        return

    avg_likes = sum(p["likes"] for p in posts) / len(posts)
    top_accounts = len(set(p["handle"] for p in posts))
    print(f"  Unique accounts: {top_accounts}  |  Avg likes: {avg_likes:.1f}  |  "
          f"Following coverage: {len(following_posts)}/{len(posts)} posts\n")

    # ── Following list posts first, grouped by tier ──────────────────────────
    if following_posts:
        print(f"  ── FROM YOUR FOLLOWING LIST ({len(following_posts)} posts) ──────────────────────")
        by_tier: dict[str, list[dict]] = {}
        for p in following_posts:
            by_tier.setdefault(p["tier"], []).append(p)
        for tier in sorted(by_tier, key=lambda t: TIER_ORDER.get(t, 9)):
            print(f"\n  [{_tier_label(tier)}]")
            for p in sorted(by_tier[tier], key=lambda x: x["created_at"], reverse=True):
                weight_str = f"  weight={p['weight']}" if p["weight"] else ""
                print(f"\n  {p['handle']}{weight_str}  —  {_fmt_time(p['created_at'])}")
                print(f"  👍 {p['likes']}  🔁 {p['retweets']}  👁 {p['impressions']:,}")
                for line in p["text"].split("\n"):
                    print(f"    {line}")
                print(f"  {p['url']}")

    # ── Top public posts by likes ─────────────────────────────────────────────
    top_public = public_posts[:10]
    if top_public:
        print(f"\n  ── TOP PUBLIC POSTS (by likes, top {len(top_public)}) ─────────────────────")
        for p in top_public:
            print(f"\n  {p['handle']}  —  {_fmt_time(p['created_at'])}")
            print(f"  👍 {p['likes']}  🔁 {p['retweets']}  👁 {p['impressions']:,}")
            for line in p["text"].split("\n"):
                print(f"    {line}")
            print(f"  {p['url']}")

    print(f"\n{'='*65}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Ticker symbol, e.g. SMR")
    parser.add_argument("--since-hours", type=int, default=48)
    parser.add_argument("--max-results", type=int, default=100)
    args = parser.parse_args()

    posts = search_ticker(args.ticker, args.since_hours, args.max_results)
    print_report(args.ticker, posts, args.since_hours)


if __name__ == "__main__":
    main()
