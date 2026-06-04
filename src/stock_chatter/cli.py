from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .accounts import usernames
from .backtest import BACKTEST_FIELDS, backtest_accounts
from .dashboard import write_dashboard
from .io_utils import append_new_jsonl, read_csv_dicts, read_jsonl, write_csv_dicts, write_text
from .memo import render_memo
from .prices import fetch_yfinance_prices, tickers_from_signals
from .run_log import log_run, new_run_id
from .scoring import attach_forward_returns, filter_signals_by_lookback, score_accounts
from .setups import (
    LEADERBOARD_FIELDS,
    SETUP_FIELDS,
    WATCHLIST_FIELDS,
    build_account_leaderboard,
    classify_ticker_setups,
    update_watchlist_memory,
)
from .signals import extract_signals
from .state import get_timestamp, load_state, save_state, set_max_timestamp, set_timestamp
from .x_api import XApiError, XCostApprovalRequired, estimate_recent_search, fetch_recent_cashtag_posts

POSTS_PATH = Path("data/raw/x_posts.jsonl")
SIGNALS_PATH = Path("data/interim/signals.csv")
PRICES_PATH = Path("data/prices/ohlcv.csv")
SCORED_SIGNALS_PATH = Path("data/interim/scored_signals.csv")
SCORES_PATH = Path("reports/account_scores.csv")
SETUPS_PATH = Path("reports/ticker_setups.csv")
WATCHLIST_PATH = Path("reports/watchlist_memory.csv")
LEADERBOARD_PATH = Path("reports/account_leaderboard.csv")
BACKTEST_PATH = Path("reports/account_backtest.csv")
UNSUPPORTED_TICKERS_PATH = Path("reports/unsupported_tickers.csv")
MEMO_PATH = Path("reports/latest_memo.md")
DASHBOARD_PATH = Path("reports/dashboard.html")

SIGNAL_FIELDS = [
    "account",
    "account_tier",
    "account_weight",
    "tweet_id",
    "tweet_created_at",
    "ticker",
    "action",
    "direction",
    "confidence",
    "catalysts",
    "hype_score",
    "url",
    "text",
]

SCORE_FIELDS = [
    "account",
    "call_count",
    "complete_20d_count",
    "avg_ret_5d",
    "avg_ret_20d",
    "hit_rate_20d",
    "avg_max_drawdown_20d",
    "avg_hype_score",
    "trust_score",
    "status",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stock-chatter")
    subparsers = parser.add_subparsers(dest="command", required=True)

    estimate = subparsers.add_parser("estimate-x", help="Estimate X API calls without contacting X.")
    estimate.add_argument("--since-hours", type=int, default=24)
    estimate.add_argument("--max-pages", type=int, default=1)

    fetch = subparsers.add_parser("fetch-x", help="Fetch recent X posts after explicit cost approval.")
    fetch.add_argument("--since-hours", type=int, default=24)
    fetch.add_argument("--since-last", action="store_true")
    fetch.add_argument("--start-time", help="Explicit UTC ISO start time, for example 2026-05-01T00:00:00Z.")
    fetch.add_argument("--end-time", help="Explicit UTC ISO end time, for example 2026-05-02T00:00:00Z.")
    fetch.add_argument("--max-pages", type=int, default=1)
    fetch.add_argument("--end-lag-seconds", type=int, default=15)
    fetch.add_argument("--approve-x-cost", action="store_true")
    fetch.add_argument("--daily-budget-usd", type=float, default=1.0)
    fetch.add_argument("--assumed-post-read-cost-usd", type=float, default=0.005)
    fetch.add_argument("--out", default=str(POSTS_PATH))

    extract = subparsers.add_parser("extract-signals", help="Extract ticker signals from saved X posts.")
    extract.add_argument("--posts", default=str(POSTS_PATH))
    extract.add_argument("--out", default=str(SIGNALS_PATH))

    prices = subparsers.add_parser("fetch-prices", help="Fetch yfinance OHLCV for signal tickers.")
    prices.add_argument("--signals", default=str(SIGNALS_PATH))
    prices.add_argument("--start", required=True)
    prices.add_argument("--end", required=True)
    prices.add_argument("--out", default=str(PRICES_PATH))
    prices.add_argument("--unsupported-out", default=str(UNSUPPORTED_TICKERS_PATH))

    score = subparsers.add_parser("score", help="Score signals and accounts from local prices.")
    score.add_argument("--signals", default=str(SIGNALS_PATH))
    score.add_argument("--prices", default=str(PRICES_PATH))
    score.add_argument("--lookback-days", type=int, default=90)
    score.add_argument("--scored-signals-out", default=str(SCORED_SIGNALS_PATH))
    score.add_argument("--scores-out", default=str(SCORES_PATH))

    setups = subparsers.add_parser("classify-setups", help="Classify ticker setups from signals and price context.")
    setups.add_argument("--signals", default=str(SIGNALS_PATH))
    setups.add_argument("--prices", default=str(PRICES_PATH))
    setups.add_argument("--out", default=str(SETUPS_PATH))

    watchlist = subparsers.add_parser("update-watchlist", help="Update ticker watchlist memory from setup rows.")
    watchlist.add_argument("--setups", default=str(SETUPS_PATH))
    watchlist.add_argument("--memory", default=str(WATCHLIST_PATH))
    watchlist.add_argument("--out", default=str(WATCHLIST_PATH))

    leaderboard = subparsers.add_parser("leaderboard", help="Build an account leaderboard from signals and setup rows.")
    leaderboard.add_argument("--signals", default=str(SIGNALS_PATH))
    leaderboard.add_argument("--setups", default=str(SETUPS_PATH))
    leaderboard.add_argument("--out", default=str(LEADERBOARD_PATH))

    backtest = subparsers.add_parser("backtest", help="Backtest account trust from timestamped signals and local prices.")
    backtest.add_argument("--signals", default=str(SIGNALS_PATH))
    backtest.add_argument("--prices", default=str(PRICES_PATH))
    backtest.add_argument("--out", default=str(BACKTEST_PATH))

    memo = subparsers.add_parser("memo", help="Render memo from local signals and scores.")
    memo.add_argument("--signals", default=str(SIGNALS_PATH))
    memo.add_argument("--scores", default=str(SCORES_PATH))
    memo.add_argument("--setups", default=str(SETUPS_PATH))
    memo.add_argument("--leaderboard", default=str(LEADERBOARD_PATH))
    memo.add_argument("--watchlist", default=str(WATCHLIST_PATH))
    memo.add_argument("--backtest", default=str(BACKTEST_PATH))
    memo.add_argument("--out", default=str(MEMO_PATH))
    memo.add_argument("--since-last", action="store_true")
    memo.add_argument("--x-skipped", action="store_true")
    memo.add_argument("--type", default="US Stock Chatter Memo")

    dashboard = subparsers.add_parser("dashboard", help="Render an interactive static HTML dashboard.")
    dashboard.add_argument("--signals", default=str(SIGNALS_PATH))
    dashboard.add_argument("--setups", default=str(SETUPS_PATH))
    dashboard.add_argument("--leaderboard", default=str(LEADERBOARD_PATH))
    dashboard.add_argument("--watchlist", default=str(WATCHLIST_PATH))
    dashboard.add_argument("--backtest", default=str(BACKTEST_PATH))
    dashboard.add_argument("--out", default=str(DASHBOARD_PATH))

    repair = subparsers.add_parser("repair-state", help="Repair local state from saved raw posts without calling external APIs.")
    repair.add_argument("--posts", default=str(POSTS_PATH))

    daily = subparsers.add_parser("daily-pipeline", help="Run local extraction, setup classification, memory, leaderboard, and memo rendering.")
    daily.add_argument("--posts", default=str(POSTS_PATH))
    daily.add_argument("--signals", default=str(SIGNALS_PATH))
    daily.add_argument("--prices", default=str(PRICES_PATH))
    daily.add_argument("--setups", default=str(SETUPS_PATH))
    daily.add_argument("--watchlist", default=str(WATCHLIST_PATH))
    daily.add_argument("--leaderboard", default=str(LEADERBOARD_PATH))
    daily.add_argument("--backtest", default=str(BACKTEST_PATH))
    daily.add_argument("--unsupported-tickers", default=str(UNSUPPORTED_TICKERS_PATH))
    daily.add_argument("--memo", default=str(MEMO_PATH))
    daily.add_argument("--dashboard", default=str(DASHBOARD_PATH))
    daily.add_argument("--fetch-prices", action="store_true")
    daily.add_argument("--price-start")
    daily.add_argument("--price-end")
    daily.add_argument("--x-skipped", action="store_true")
    daily.add_argument("--type", default="US Stock Chatter Memo")

    args = parser.parse_args(argv)

    if args.command == "estimate-x":
        print(estimate_recent_search(usernames(), max_pages=args.max_pages).human())
        print(f"Window: last {args.since_hours} hour(s). No X API call was made.")
        return 0

    if args.command == "fetch-x":
        run_id = new_run_id()
        state = load_state()
        explicit_window = bool(args.start_time or args.end_time)
        if args.start_time or args.end_time:
            if not args.start_time or not args.end_time:
                raise SystemExit("--start-time and --end-time must be supplied together")
            start_time = _parse_utc(args.start_time)
            end_time = _parse_utc(args.end_time)
        else:
            end_time = datetime.now(timezone.utc) - timedelta(seconds=args.end_lag_seconds)
            start_time = get_timestamp(state, "last_x_fetch_at") if args.since_last else None
            start_time = start_time or end_time - timedelta(hours=args.since_hours)
            if not args.since_last and args.since_hours >= 168:
                start_time += timedelta(minutes=5)
        estimate = estimate_recent_search(usernames(), max_pages=args.max_pages)
        estimated_cost = estimate.max_requests * 100 * args.assumed_post_read_cost_usd
        budget_key = f"x_estimated_spend_usd_{datetime.now(timezone.utc).date().isoformat()}"
        used_today = float(state.get(budget_key, 0.0))
        if used_today + estimated_cost > args.daily_budget_usd:
            log_run(
                "x_fetch_blocked_budget",
                run_id=run_id,
                used_estimate_usd=f"{used_today:.2f}",
                new_estimate_usd=f"{estimated_cost:.2f}",
                daily_budget_usd=f"{args.daily_budget_usd:.2f}",
            )
            print(
                f"X API budget guard stopped the run: used_estimate=${used_today:.2f}, "
                f"new_estimate=${estimated_cost:.2f}, daily_budget=${args.daily_budget_usd:.2f}."
            )
            print("No X API call was made.")
            return 2
        if args.approve_x_cost:
            state[budget_key] = f"{used_today + estimated_cost:.2f}"
            save_state(state)
        try:
            rows = fetch_recent_cashtag_posts(
                start_time=start_time,
                end_time=end_time,
                handles=usernames(),
                max_pages=args.max_pages,
                approve_cost=args.approve_x_cost,
            )
        except XCostApprovalRequired as exc:
            log_run("x_fetch_missing_approval", run_id=run_id, estimate=estimate.human())
            print(str(exc))
            print("No X API call was made. Re-run with --approve-x-cost only after approving this cost risk.")
            return 2
        except XApiError as exc:
            if args.approve_x_cost:
                state[budget_key] = f"{used_today:.2f}"
                save_state(state)
            log_run("x_fetch_error", run_id=run_id, error=str(exc), estimated_cost_usd=f"{estimated_cost:.2f}")
            print(str(exc))
            print("No X post rows were saved.")
            return 1
        count = append_new_jsonl(args.out, _dedupe_rows(rows))
        max_row_timestamp = _max_post_timestamp(rows)
        if explicit_window:
            set_timestamp(state, "last_x_backfill_at", end_time)
            set_max_timestamp(state, "last_x_fetch_at", max_row_timestamp)
        else:
            set_max_timestamp(state, "last_x_fetch_at", max_row_timestamp or end_time)
        save_state(state)
        log_run(
            "x_fetch_success",
            run_id=run_id,
            row_count=str(len(rows)),
            appended_count=str(count),
            estimated_cost_usd=f"{estimated_cost:.2f}",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )
        print(f"Fetched and appended {count} X post row(s) to {args.out}.")
        return 0

    if args.command == "extract-signals":
        rows = extract_signals(read_jsonl(args.posts))
        count = write_csv_dicts(args.out, rows, SIGNAL_FIELDS)
        print(f"Wrote {count} signal row(s) to {args.out}.")
        return 0

    if args.command == "fetch-prices":
        signals = read_csv_dicts(args.signals)
        tickers = tickers_from_signals(signals)
        count = fetch_yfinance_prices(tickers, args.start, args.end, args.out, unsupported_out_path=args.unsupported_out)
        log_run(
            "price_fetch_success",
            ticker_count=str(len(tickers)),
            price_row_count=str(count),
            unsupported_out=args.unsupported_out,
        )
        print(f"Wrote {count} price row(s) for {len(tickers)} ticker(s) to {args.out}.")
        return 0

    if args.command == "score":
        signals = filter_signals_by_lookback(read_csv_dicts(args.signals), args.lookback_days)
        prices = read_csv_dicts(args.prices)
        scored = attach_forward_returns(signals, prices)
        write_csv_dicts(args.scored_signals_out, scored, SIGNAL_FIELDS + ["entry_date", "entry_open", "ret_1d", "ret_5d", "ret_20d", "ret_60d", "max_drawdown_20d"])
        scores = score_accounts(signals, prices, lookback_days=None)
        count = write_csv_dicts(args.scores_out, scores, SCORE_FIELDS)
        print(f"Wrote {count} account score row(s) to {args.scores_out}.")
        return 0

    if args.command == "classify-setups":
        setup_rows = classify_ticker_setups(read_csv_dicts(args.signals), read_csv_dicts(args.prices))
        count = write_csv_dicts(args.out, setup_rows, SETUP_FIELDS)
        print(f"Wrote {count} ticker setup row(s) to {args.out}.")
        return 0

    if args.command == "update-watchlist":
        memory_rows = update_watchlist_memory(read_csv_dicts(args.memory), read_csv_dicts(args.setups))
        count = write_csv_dicts(args.out, memory_rows, WATCHLIST_FIELDS)
        print(f"Wrote {count} watchlist memory row(s) to {args.out}.")
        return 0

    if args.command == "leaderboard":
        rows = build_account_leaderboard(read_csv_dicts(args.signals), read_csv_dicts(args.setups))
        count = write_csv_dicts(args.out, rows, LEADERBOARD_FIELDS)
        print(f"Wrote {count} account leaderboard row(s) to {args.out}.")
        return 0

    if args.command == "backtest":
        rows = backtest_accounts(read_csv_dicts(args.signals), read_csv_dicts(args.prices))
        count = write_csv_dicts(args.out, rows, BACKTEST_FIELDS)
        print(f"Wrote {count} account backtest row(s) to {args.out}.")
        return 0

    if args.command == "memo":
        state = load_state()
        since = state.get("last_memo_at") if args.since_last else None
        text = render_memo(
            signals=read_csv_dicts(args.signals),
            scores=read_csv_dicts(args.scores),
            x_skipped=args.x_skipped,
            setups=read_csv_dicts(args.setups),
            leaderboard=read_csv_dicts(args.leaderboard),
            watchlist=read_csv_dicts(args.watchlist),
            backtest=read_csv_dicts(args.backtest),
            memo_type=args.type,
            since=since,
        )
        write_text(args.out, text)
        set_timestamp(state, "last_memo_at")
        save_state(state)
        print(f"Wrote memo to {args.out}.")
        return 0

    if args.command == "dashboard":
        write_dashboard(
            args.out,
            setups=read_csv_dicts(args.setups),
            leaderboard=read_csv_dicts(args.leaderboard),
            watchlist=read_csv_dicts(args.watchlist),
            signals=read_csv_dicts(args.signals),
            backtest=read_csv_dicts(args.backtest),
        )
        print(f"Wrote dashboard to {args.out}.")
        return 0

    if args.command == "repair-state":
        rows = read_jsonl(args.posts)
        max_timestamp = _max_post_timestamp(rows)
        state = load_state()
        set_max_timestamp(state, "last_x_fetch_at", max_timestamp)
        save_state(state)
        log_run("state_repaired", max_post_timestamp=max_timestamp.isoformat() if max_timestamp else "")
        print(f"Repaired state from {len(rows)} raw post row(s).")
        return 0

    if args.command == "daily-pipeline":
        run_id = new_run_id()
        signals = extract_signals(read_jsonl(args.posts))
        write_csv_dicts(args.signals, signals, SIGNAL_FIELDS)
        if args.fetch_prices:
            if not args.price_start or not args.price_end:
                raise SystemExit("--price-start and --price-end are required with --fetch-prices")
            tickers = tickers_from_signals(signals)
            fetch_yfinance_prices(tickers, args.price_start, args.price_end, args.prices, unsupported_out_path=args.unsupported_tickers)
        prices = read_csv_dicts(args.prices)
        setup_rows = classify_ticker_setups(signals, prices)
        write_csv_dicts(args.setups, setup_rows, SETUP_FIELDS)
        memory_rows = update_watchlist_memory(read_csv_dicts(args.watchlist), setup_rows)
        write_csv_dicts(args.watchlist, memory_rows, WATCHLIST_FIELDS)
        leaderboard_rows = build_account_leaderboard(signals, setup_rows)
        write_csv_dicts(args.leaderboard, leaderboard_rows, LEADERBOARD_FIELDS)
        backtest_rows = backtest_accounts(signals, prices)
        write_csv_dicts(args.backtest, backtest_rows, BACKTEST_FIELDS)
        text = render_memo(
            signals=signals,
            scores=read_csv_dicts(SCORES_PATH),
            x_skipped=args.x_skipped,
            setups=setup_rows,
            leaderboard=leaderboard_rows,
            watchlist=memory_rows,
            backtest=backtest_rows,
            memo_type=args.type,
        )
        write_text(args.memo, text)
        write_dashboard(
            args.dashboard,
            setups=setup_rows,
            leaderboard=leaderboard_rows,
            watchlist=memory_rows,
            signals=signals,
            backtest=backtest_rows,
        )
        state = load_state()
        set_timestamp(state, "last_memo_at")
        save_state(state)
        log_run(
            "daily_pipeline_success",
            run_id=run_id,
            signal_count=str(len(signals)),
            setup_count=str(len(setup_rows)),
            watchlist_count=str(len(memory_rows)),
            memo=args.memo,
            dashboard=args.dashboard,
        )
        print(f"Wrote daily pipeline outputs, memo to {args.memo}, and dashboard to {args.dashboard}.")
        return 0

    raise AssertionError(f"Unhandled command {args.command}")


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for row in rows:
        row_id = row.get("id")
        if row_id and row_id not in seen:
            seen.add(row_id)
            deduped.append(row)
    return deduped


def _max_post_timestamp(rows: list[dict]) -> datetime | None:
    timestamps = []
    for row in rows:
        value = row.get("created_at") or row.get("tweet_created_at")
        if not value:
            continue
        try:
            timestamps.append(_parse_utc(value))
        except ValueError:
            continue
    return max(timestamps) if timestamps else None


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
