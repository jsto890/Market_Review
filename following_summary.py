#!/usr/bin/env python3
"""
Summarise what the monitored following list has been posting lately.

Reads from the locally cached x_posts.jsonl — no API call needed.
Groups by account tier and shows each account's recent tickers + excerpts.

Usage:
    python following_summary.py [--since-hours 72] [--tier core_alpha]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from stock_chatter.accounts import ACCOUNTS, account_for_handle
from stock_chatter.signals import extract_tickers_from_post

POSTS_FILE = Path(__file__).parent / "data/raw/x_posts.jsonl"
TIER_ORDER = ["core_alpha", "swing_watchlist", "long_term_research", "sentiment_noise"]
TIER_LABEL = {
    "core_alpha":       "CORE ALPHA",
    "swing_watchlist":  "SWING WATCHLIST",
    "long_term_research": "LONG TERM RESEARCH",
    "sentiment_noise":  "SENTIMENT NOISE",
}
ACCOUNT_MAP = {a.handle.lower(): a for a in ACCOUNTS}


def _fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %H:%M")
    except Exception:
        return iso[:16]


def load_posts(since_hours: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    posts = []
    if not POSTS_FILE.exists():
        sys.exit(f"Posts file not found: {POSTS_FILE}")
    with POSTS_FILE.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                p = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                dt = datetime.fromisoformat(p.get("created_at", "").replace("Z", "+00:00"))
                if dt >= cutoff:
                    posts.append(p)
            except Exception:
                continue
    return posts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-hours", type=int, default=72)
    parser.add_argument("--tier", choices=TIER_ORDER, default=None,
                        help="Filter to a specific tier")
    args = parser.parse_args()

    posts = load_posts(args.since_hours)
    if not posts:
        print(f"No posts found in the last {args.since_hours}h. Run fetch-x to update.")
        return

    # Group by account
    by_account: dict[str, list[dict]] = defaultdict(list)
    for p in posts:
        handle = p.get("account", "").lower()
        if handle in ACCOUNT_MAP:
            by_account[handle].append(p)

    tiers_to_show = [args.tier] if args.tier else TIER_ORDER

    print(f"\n{'='*65}")
    print(f"  Following list activity  —  last {args.since_hours}h")
    print(f"  {len(posts)} posts from {len(by_account)} accounts")
    print(f"{'='*65}")

    for tier in tiers_to_show:
        accounts_in_tier = [a for a in ACCOUNTS if a.tier == tier
                            and a.handle.lower() in by_account]
        if not accounts_in_tier:
            continue

        print(f"\n  ── {TIER_LABEL[tier]} ──────────────────────────────────────────")

        for acct in sorted(accounts_in_tier, key=lambda a: -a.score_weight):
            acct_posts = sorted(by_account[acct.handle.lower()],
                                key=lambda p: p.get("created_at", ""), reverse=True)

            # Aggregate tickers mentioned
            ticker_counts: dict[str, int] = defaultdict(int)
            for p in acct_posts:
                for t in extract_tickers_from_post(p):
                    ticker_counts[t] += 1
            top_tickers = sorted(ticker_counts, key=lambda t: -ticker_counts[t])[:8]

            print(f"\n  {acct.handle}  (weight={acct.score_weight}  |  {acct.purpose})")
            print(f"  {len(acct_posts)} posts  |  tickers: {' '.join('$'+t for t in top_tickers) or 'none'}")

            # Show up to 4 most recent posts
            for p in acct_posts[:4]:
                metrics = p.get("public_metrics", {})
                likes = metrics.get("like_count", 0)
                impressions = metrics.get("impression_count", 0)
                text = p.get("text", "").replace("\n", " ").strip()
                if len(text) > 160:
                    text = text[:157] + "..."
                print(f"\n    [{_fmt_time(p.get('created_at',''))}]  👍{likes}  👁{impressions:,}")
                print(f"    {text}")
                print(f"    {p.get('url','')}")

    print(f"\n{'='*65}\n")


if __name__ == "__main__":
    main()
