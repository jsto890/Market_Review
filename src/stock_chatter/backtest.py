from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean

from .scoring import attach_forward_returns

BACKTEST_FIELDS = [
    "account",
    "account_tier",
    "signal_count",
    "actionable_count",
    "entry_count",
    "short_count",
    "exit_count",
    "watch_count",
    "mention_count",
    "distinct_ticker_count",
    "first_mention_count",
    "complete_1d_count",
    "complete_5d_count",
    "complete_20d_count",
    "avg_ret_1d",
    "avg_ret_5d",
    "avg_ret_20d",
    "avg_excess_ret_1d",
    "avg_excess_ret_5d",
    "avg_excess_ret_20d",
    "hit_rate_1d",
    "hit_rate_5d",
    "hit_rate_20d",
    "avg_max_drawdown_20d",
    "avg_hype_score",
    "avg_account_weight",
    "trust_score",
    "trust_label",
    "evidence_status",
    "top_tickers",
]

TRADE_ACTIONS = {"entry", "short"}


def backtest_accounts(signals: list[dict], prices: list[dict]) -> list[dict]:
    scored = attach_forward_returns(signals, prices)
    price_by_ticker = _prices_by_ticker(prices)
    first_by_ticker = _first_signal_by_ticker(scored)
    by_account: dict[str, list[dict]] = defaultdict(list)
    for signal in scored:
        account = signal.get("account", "")
        if account:
            by_account[account].append(signal)

    rows: list[dict] = []
    for account, account_signals in by_account.items():
        tickers = [row.get("ticker", "").upper() for row in account_signals if row.get("ticker")]
        actions = Counter(row.get("action", "mention") for row in account_signals)
        trade_signals = _dedupe_trade_events([row for row in account_signals if row.get("action") in TRADE_ACTIONS])
        _attach_benchmark_returns(trade_signals, price_by_ticker)
        completed_1d = _completed(trade_signals, "ret_1d")
        completed_5d = _completed(trade_signals, "ret_5d")
        completed_20d = _completed(trade_signals, "ret_20d")
        first_count = sum(
            1
            for row in account_signals
            if first_by_ticker.get(row.get("ticker", "").upper()) == (row.get("tweet_created_at", ""), account)
        )
        avg_1d = _avg(completed_1d, "ret_1d")
        avg_5d = _avg(completed_5d, "ret_5d")
        avg_20d = _avg(completed_20d, "ret_20d")
        avg_excess_1d = _avg(_completed(trade_signals, "excess_ret_1d"), "excess_ret_1d")
        avg_excess_5d = _avg(_completed(trade_signals, "excess_ret_5d"), "excess_ret_5d")
        avg_excess_20d = _avg(_completed(trade_signals, "excess_ret_20d"), "excess_ret_20d")
        hit_1d = _hit_rate(completed_1d, "ret_1d")
        hit_5d = _hit_rate(completed_5d, "ret_5d")
        hit_20d = _hit_rate(completed_20d, "ret_20d")
        avg_drawdown = _avg(_completed(completed_20d, "max_drawdown_20d"), "max_drawdown_20d")
        avg_hype = _avg(account_signals, "hype_score")
        avg_weight = _avg(account_signals, "account_weight")
        trust_score = _trust_score(
            signal_count=len(account_signals),
            actionable_count=len(trade_signals),
            distinct_ticker_count=len(set(tickers)),
            first_mention_count=first_count,
            avg_weight=avg_weight or 0.0,
            avg_hype=avg_hype or 0.0,
            avg_1d=avg_1d,
            avg_5d=avg_5d,
            avg_20d=avg_20d,
            avg_excess_1d=avg_excess_1d,
            avg_excess_5d=avg_excess_5d,
            avg_excess_20d=avg_excess_20d,
            hit_1d=hit_1d,
            hit_5d=hit_5d,
            hit_20d=hit_20d,
            avg_drawdown=avg_drawdown,
        )
        evidence_status = _evidence_status(
            complete_1d=len(completed_1d),
            complete_5d=len(completed_5d),
            complete_20d=len(completed_20d),
        )
        rows.append(
            {
                "account": account,
                "account_tier": _most_common(row.get("account_tier", "unknown") for row in account_signals),
                "signal_count": str(len(account_signals)),
                "actionable_count": str(len(trade_signals)),
                "entry_count": str(actions["entry"]),
                "short_count": str(actions["short"]),
                "exit_count": str(actions["exit"]),
                "watch_count": str(actions["watch"]),
                "mention_count": str(actions["mention"]),
                "distinct_ticker_count": str(len(set(tickers))),
                "first_mention_count": str(first_count),
                "complete_1d_count": str(len(completed_1d)),
                "complete_5d_count": str(len(completed_5d)),
                "complete_20d_count": str(len(completed_20d)),
                "avg_ret_1d": _fmt(avg_1d),
                "avg_ret_5d": _fmt(avg_5d),
                "avg_ret_20d": _fmt(avg_20d),
                "avg_excess_ret_1d": _fmt(avg_excess_1d),
                "avg_excess_ret_5d": _fmt(avg_excess_5d),
                "avg_excess_ret_20d": _fmt(avg_excess_20d),
                "hit_rate_1d": _fmt(hit_1d),
                "hit_rate_5d": _fmt(hit_5d),
                "hit_rate_20d": _fmt(hit_20d),
                "avg_max_drawdown_20d": _fmt(avg_drawdown),
                "avg_hype_score": _fmt(avg_hype),
                "avg_account_weight": _fmt(avg_weight),
                "trust_score": f"{trust_score:.2f}",
                "trust_label": _trust_label(
                    trust_score,
                    complete_1d=len(completed_1d),
                    complete_5d=len(completed_5d),
                    complete_20d=len(completed_20d),
                    signal_count=len(account_signals),
                ),
                "evidence_status": evidence_status,
                "top_tickers": ";".join(ticker for ticker, _ in Counter(tickers).most_common(8)),
            }
        )
    rows.sort(key=lambda row: float(row["trust_score"]), reverse=True)
    return rows


def _first_signal_by_ticker(scored: list[dict]) -> dict[str, tuple[str, str]]:
    first: dict[str, tuple[str, str]] = {}
    for row in sorted(scored, key=lambda item: item.get("tweet_created_at", "")):
        ticker = row.get("ticker", "").upper()
        account = row.get("account", "")
        created = row.get("tweet_created_at", "")
        if ticker and account and ticker not in first:
            first[ticker] = (created, account)
    return first


def _trust_score(
    *,
    signal_count: int,
    actionable_count: int,
    distinct_ticker_count: int,
    first_mention_count: int,
    avg_weight: float,
    avg_hype: float,
    avg_1d: float | None,
    avg_5d: float | None,
    avg_20d: float | None,
    avg_excess_1d: float | None,
    avg_excess_5d: float | None,
    avg_excess_20d: float | None,
    hit_1d: float | None,
    hit_5d: float | None,
    hit_20d: float | None,
    avg_drawdown: float | None,
) -> float:
    score = avg_weight * 2.0
    score += min(actionable_count, 25) * 0.20
    score += min(distinct_ticker_count, 20) * 0.08
    score += min(first_mention_count, 20) * 0.25
    score += min(signal_count, 40) * 0.02
    score -= avg_hype * 5.0
    if avg_1d is not None:
        score += (avg_excess_1d if avg_excess_1d is not None else avg_1d) * 20.0 + (hit_1d or 0.0) * 1.5
    if avg_5d is not None:
        score += (avg_excess_5d if avg_excess_5d is not None else avg_5d) * 70.0 + (hit_5d or 0.0) * 5.0
    if avg_20d is not None:
        score += (avg_excess_20d if avg_excess_20d is not None else avg_20d) * 140.0 + (hit_20d or 0.0) * 12.0
    if avg_drawdown is not None:
        score -= abs(avg_drawdown) * 35.0
    return score


def _trust_label(trust_score: float, *, complete_1d: int, complete_5d: int, complete_20d: int, signal_count: int) -> str:
    if complete_20d < 3 and complete_5d < 5:
        return "pending_forward_data"
    if signal_count < 5:
        return "watch"
    if complete_20d < 3:
        return "provisional_5d" if trust_score >= 8 else "watch"
    if trust_score >= 18:
        return "high_trust_recent"
    if trust_score >= 10:
        return "promising"
    if trust_score <= 3:
        return "low_signal"
    return "watch"


def _evidence_status(*, complete_1d: int, complete_5d: int, complete_20d: int) -> str:
    if complete_20d >= 3:
        return "20d_ready"
    if complete_5d >= 5:
        return "5d_provisional"
    if complete_1d:
        return "1d_only"
    return "no_forward_data"


def _dedupe_trade_events(rows: list[dict]) -> list[dict]:
    events: dict[tuple[str, str, str, str, str], dict] = {}
    for row in sorted(rows, key=lambda item: item.get("tweet_created_at", "")):
        event_date = row.get("entry_date") or row.get("tweet_created_at", "")[:10]
        key = (
            row.get("account", ""),
            row.get("ticker", "").upper(),
            row.get("action", ""),
            row.get("direction", ""),
            event_date,
        )
        events.setdefault(key, row)
    return list(events.values())


def _attach_benchmark_returns(events: list[dict], price_by_ticker: dict[str, list[dict]]) -> None:
    benchmark_prices = price_by_ticker.get("SPY") or price_by_ticker.get("QQQ") or []
    if not benchmark_prices:
        return
    for event in events:
        entry_date = event.get("entry_date")
        if not entry_date:
            continue
        for horizon in (1, 5, 20):
            event_ret = _to_float(event.get(f"ret_{horizon}d"))
            benchmark_ret = _benchmark_return(benchmark_prices, entry_date, horizon)
            if event_ret is None or benchmark_ret is None:
                continue
            if event.get("direction") == "short":
                benchmark_ret *= -1
            event[f"benchmark_ret_{horizon}d"] = f"{benchmark_ret:.6f}"
            event[f"excess_ret_{horizon}d"] = f"{event_ret - benchmark_ret:.6f}"


def _prices_by_ticker(prices: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in prices:
        ticker = row.get("ticker", "").upper()
        if ticker:
            grouped[ticker].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: row.get("date", ""))
    return grouped


def _benchmark_return(prices: list[dict], entry_date: str, horizon: int) -> float | None:
    entry_idx = None
    for idx, row in enumerate(prices):
        if row.get("date", "") >= entry_date:
            entry_idx = idx
            break
    if entry_idx is None or entry_idx + horizon >= len(prices):
        return None
    entry_open = _to_float(prices[entry_idx].get("open"))
    target_close = _to_float(prices[entry_idx + horizon].get("close"))
    if not entry_open or target_close is None:
        return None
    return target_close / entry_open - 1.0


def _completed(rows: list[dict], key: str) -> list[dict]:
    return [row for row in rows if _to_float(row.get(key)) is not None]


def _avg(rows: list[dict], key: str) -> float | None:
    values = [_to_float(row.get(key)) for row in rows]
    clean = [value for value in values if value is not None]
    return mean(clean) if clean else None


def _hit_rate(rows: list[dict], key: str) -> float | None:
    values = [_to_float(row.get(key)) for row in rows]
    clean = [value for value in values if value is not None]
    return mean(1.0 if value > 0 else 0.0 for value in clean) if clean else None


def _most_common(values) -> str:
    counts = Counter(value for value in values if value)
    return counts.most_common(1)[0][0] if counts else ""


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"
