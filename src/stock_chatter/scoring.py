from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def score_accounts(
    signals: list[dict],
    prices: list[dict],
    min_calls: int = 3,
    lookback_days: int | None = None,
    now: datetime | None = None,
) -> list[dict]:
    if lookback_days is not None:
        signals = filter_signals_by_lookback(signals, lookback_days, now=now)
    scored_signals = attach_forward_returns(signals, prices)
    by_account: dict[str, list[dict]] = defaultdict(list)
    for signal in scored_signals:
        if signal.get("action") not in {"entry", "short"}:
            continue
        by_account[signal.get("account", "")].append(signal)

    rows: list[dict] = []
    for account, account_signals in sorted(by_account.items()):
        eligible = [row for row in account_signals if _to_float(row.get("ret_20d")) is not None]
        call_count = len(account_signals)
        complete_count = len(eligible)
        avg_20d = _avg(eligible, "ret_20d")
        avg_5d = _avg(eligible, "ret_5d")
        hit_20d = _hit_rate(eligible, "ret_20d")
        avg_drawdown = _avg(eligible, "max_drawdown_20d")
        avg_hype = _avg(account_signals, "hype_score")
        base = (avg_20d or 0.0) * 100 + (hit_20d or 0.0) * 25 - abs(avg_drawdown or 0.0) * 30
        base -= (avg_hype or 0.0) * 8
        status = "trusted" if complete_count >= min_calls and base > 0 else "watch"
        if complete_count == 0:
            status = "pending_returns"
        rows.append(
            {
                "account": account,
                "call_count": str(call_count),
                "complete_20d_count": str(complete_count),
                "avg_ret_5d": _fmt(avg_5d),
                "avg_ret_20d": _fmt(avg_20d),
                "hit_rate_20d": _fmt(hit_20d),
                "avg_max_drawdown_20d": _fmt(avg_drawdown),
                "avg_hype_score": _fmt(avg_hype),
                "trust_score": f"{base:.2f}",
                "status": status,
            }
        )
    rows.sort(key=lambda row: float(row["trust_score"]), reverse=True)
    return rows


def filter_signals_by_lookback(signals: list[dict], lookback_days: int, now: datetime | None = None) -> list[dict]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(days=lookback_days)
    filtered: list[dict] = []
    for signal in signals:
        created = signal.get("tweet_created_at")
        if not created:
            continue
        try:
            created_at = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            continue
        if created_at >= cutoff:
            filtered.append(signal)
    return filtered


def attach_forward_returns(signals: list[dict], prices: list[dict]) -> list[dict]:
    price_by_ticker: dict[str, list[dict]] = defaultdict(list)
    for row in prices:
        price_by_ticker[row["ticker"].upper()].append(row)
    for rows in price_by_ticker.values():
        rows.sort(key=lambda row: row["date"])

    scored: list[dict] = []
    for signal in signals:
        row = dict(signal)
        ticker_prices = price_by_ticker.get(signal.get("ticker", "").upper(), [])
        entry_idx = _entry_index(signal.get("tweet_created_at", ""), ticker_prices)
        if entry_idx is None:
            scored.append(row)
            continue
        entry_open = _to_float(ticker_prices[entry_idx].get("open"))
        if not entry_open:
            scored.append(row)
            continue
        direction = signal.get("direction")
        for horizon in (1, 5, 20, 60):
            target_idx = entry_idx + horizon
            if target_idx < len(ticker_prices):
                target_close = _to_float(ticker_prices[target_idx].get("close"))
                if target_close is not None:
                    value = (target_close - entry_open) / entry_open
                    if direction == "short":
                        value *= -1
                    row[f"ret_{horizon}d"] = f"{value:.6f}"
        if entry_idx + 20 < len(ticker_prices):
            dd = _max_drawdown(ticker_prices, entry_idx, entry_idx + 20, entry_open, direction)
            if dd is not None:
                row["max_drawdown_20d"] = f"{dd:.6f}"
        row["entry_date"] = ticker_prices[entry_idx]["date"]
        row["entry_open"] = f"{entry_open:.6f}"
        scored.append(row)
    return scored


def _entry_index(created_at: str, prices: list[dict]) -> int | None:
    if not created_at or not prices:
        return None
    timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(NY)
    tweet_date = timestamp.date()
    same_day_allowed = timestamp.hour < 9 or (timestamp.hour == 9 and timestamp.minute < 30)
    for index, price in enumerate(prices):
        try:
            price_date = datetime.fromisoformat(price["date"]).date()
        except (ValueError, TypeError):
            continue
        if same_day_allowed and price_date >= tweet_date:
            return index
        if price_date > tweet_date:
            return index
    return None


def _max_drawdown(prices: list[dict], start: int, end: int, entry_open: float, direction: str) -> float | None:
    if start >= len(prices) or end < start:
        return None
    window = prices[start + 1 : end + 1]
    if not window:
        return None
    if direction == "short":
        max_high = max((_to_float(row.get("high")) or entry_open) for row in window)
        return (entry_open - max_high) / entry_open
    min_low = min((_to_float(row.get("low")) or entry_open) for row in window)
    return (min_low - entry_open) / entry_open


def _avg(rows: list[dict], key: str) -> float | None:
    values = [_to_float(row.get(key)) for row in rows]
    values = [value for value in values if value is not None]
    return mean(values) if values else None


def _hit_rate(rows: list[dict], key: str) -> float | None:
    values = [_to_float(row.get(key)) for row in rows]
    values = [value for value in values if value is not None]
    return mean(1.0 if value > 0 else 0.0 for value in values) if values else None


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"
