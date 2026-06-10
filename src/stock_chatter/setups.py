from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean

from .accounts import CLUSTER_CONFIRM, CLUSTER_CORE
from .tickers import asset_type, asset_warning

SETUP_FIELDS = [
    "ticker",
    "asset_type",
    "setup_label",
    "conviction",
    "actionability",
    "actionability_rank",
    "confidence_label",
    "warnings",
    "reason",
    "mention_count",
    "distinct_account_count",
    "source_score",
    "quality_score",
    "cluster_overlap",
    "cluster_confirmed",
    "cluster_bonus",
    "entry_count",
    "watch_count",
    "exit_count",
    "short_count",
    "avg_hype_score",
    "catalysts",
    "news_confirmation",
    "first_seen_at",
    "latest_mention_at",
    "first_account",
    "top_accounts",
    "price_data_available",
    "price_date",
    "prior_ret_1d",
    "prior_ret_5d",
    "prior_ret_20d",
    "current_gap",
    "relative_volume",
    "distance_from_20d_high",
    "max_drawdown_20d",
    "co_mentions",
]

WATCHLIST_FIELDS = [
    "ticker",
    "first_seen_at",
    "first_account",
    "first_setup_label",
    "latest_seen_at",
    "previous_setup_label",
    "latest_setup_label",
    "label_changed",
    "conviction",
    "entry_signal",
    "entry_type",
    "latest_quality_score",
    "catalysts",
    "status",
    "still_fresh",
    "age_days",
    "mention_count",
]

LEADERBOARD_FIELDS = [
    "account",
    "account_tier",
    "mention_count",
    "distinct_ticker_count",
    "entry_count",
    "first_mention_count",
    "weighted_signal_score",
    "avg_ticker_quality_score",
    "avg_hype_score",
    "leaderboard_score",
    "top_tickers",
]

CATALYST_TO_NEWS = {
    "earnings": "earnings",
    "analyst": "analyst",
    "filing": "filing",
    "mna": "m&a",
    "macro": "macro",
    "ai_infrastructure": "sector",
    "semis": "sector",
    "biotech": "sector",
    "crypto": "sector",
}

FRESH_LABELS = {"fresh_watch", "building"}
ACTIVE_LABELS = {"fresh_watch", "building", "momentum_confirmed"}
CHASE_LABELS = {"extended", "late_chase"}

# Lifecycle zones for the entry-on-transition signal.
WATCH_LABELS = {"fresh_watch", "building"}                       # staking it out, no entry yet
BREAKOUT_LABELS = {"momentum_confirmed", "extended", "late_chase"}  # price has confirmed → entry zone


def _conviction(summary: dict) -> str:
    """Signal-only conviction tier (high/med/low) — independent of price stage.

    Lets price-stage labels (extended/late_chase) stay aware of how good the
    underlying idea is, instead of being conviction-blind."""
    source_score = summary["source_score"]
    accounts = summary["distinct_account_count"]
    has_catalyst = bool(summary["catalysts"])
    cluster = summary["cluster_confirmed"]
    if source_score >= 1.25 and has_catalyst and (accounts >= 2 or cluster):
        return "high"
    if (source_score >= 1.0 and has_catalyst) or accounts >= 2:
        return "med"
    return "low"


def classify_ticker_setups(signals: list[dict], prices: list[dict]) -> list[dict]:
    price_by_ticker = _prices_by_ticker(prices)
    signals_by_ticker: dict[str, list[dict]] = defaultdict(list)
    for signal in signals:
        ticker = (signal.get("ticker") or "").upper()
        if ticker:
            signals_by_ticker[ticker].append(signal)

    rows: list[dict] = []
    for ticker, ticker_signals in sorted(signals_by_ticker.items()):
        summary = _summarize_signals(ticker_signals)
        price_context = _price_context(price_by_ticker.get(ticker, []))
        label, reason = _label_setup(summary, price_context)
        quality_score, cluster_bonus = _quality_score(summary, price_context, label)
        warnings = _warnings(ticker, summary, price_context, label)
        rows.append(
            {
                "ticker": ticker,
                "asset_type": asset_type(ticker),
                "setup_label": label,
                "conviction": _conviction(summary),
                "actionability": _actionability(label),
                "actionability_rank": str(_actionability_rank(label, price_context, warnings)),
                "confidence_label": _confidence_label(summary, price_context, warnings),
                "warnings": ";".join(warnings),
                "reason": reason,
                "mention_count": str(summary["mention_count"]),
                "distinct_account_count": str(summary["distinct_account_count"]),
                "source_score": _fmt(summary["source_score"]),
                "quality_score": _fmt(quality_score),
                "cluster_overlap": str(summary["cluster_overlap"]),
                "cluster_confirmed": "true" if summary["cluster_confirmed"] else "false",
                "cluster_bonus": _fmt(cluster_bonus),
                "entry_count": str(summary["entry_count"]),
                "watch_count": str(summary["watch_count"]),
                "exit_count": str(summary["exit_count"]),
                "short_count": str(summary["short_count"]),
                "avg_hype_score": _fmt(summary["avg_hype_score"]),
                "catalysts": ";".join(summary["catalysts"]),
                "news_confirmation": ";".join(summary["news_confirmation"]),
                "first_seen_at": summary["first_seen_at"],
                "latest_mention_at": summary["latest_mention_at"],
                "first_account": summary["first_account"],
                "top_accounts": ";".join(summary["top_accounts"]),
                "co_mentions": ",".join(summary["co_mentions"]),
                **price_context,
            }
        )
    rows.sort(key=lambda row: float(row["quality_score"]), reverse=True)
    return rows


def update_watchlist_memory(existing_rows: list[dict], setup_rows: list[dict]) -> list[dict]:
    memory = {row.get("ticker", "").upper(): dict(row) for row in existing_rows if row.get("ticker")}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for setup in setup_rows:
        ticker = setup["ticker"]
        prior = memory.get(ticker, {})
        setup_first = setup.get("first_seen_at") or now
        prior_first = prior.get("first_seen_at")
        if prior_first and prior_first <= setup_first:
            first_seen = prior_first
            first_account = prior.get("first_account") or setup.get("first_account", "")
            first_label = prior.get("first_setup_label") or setup.get("setup_label", "")
        else:
            first_seen = setup_first
            first_account = setup.get("first_account", "") or prior.get("first_account", "")
            first_label = setup.get("setup_label", "") or prior.get("first_setup_label", "")
        catalysts = _merge_tokens(prior.get("catalysts", ""), setup.get("catalysts", ""))
        latest_label = setup.get("setup_label", "")
        previous_label = prior.get("latest_setup_label", "")
        conviction = setup.get("conviction", "low")
        latest_seen = _max_iso(prior.get("latest_seen_at", ""), setup.get("latest_mention_at") or setup_first)
        # Entry signal = the watch→breakout transition with a real idea behind it.
        # This is the one-shot buy trigger, not a daily state.
        entry_fired = (
            previous_label in WATCH_LABELS
            and latest_label in BREAKOUT_LABELS
            and conviction in {"med", "high"}
        )
        entry_type = ""
        if entry_fired:
            entry_type = "primary" if latest_label == "momentum_confirmed" else "chase"
        memory[ticker] = {
            "ticker": ticker,
            "first_seen_at": first_seen,
            "first_account": first_account,
            "first_setup_label": first_label,
            "latest_seen_at": latest_seen or now,
            "previous_setup_label": previous_label,
            "latest_setup_label": latest_label,
            "label_changed": "true" if previous_label and previous_label != latest_label else "false",
            "conviction": conviction,
            "entry_signal": "true" if entry_fired else "false",
            "entry_type": entry_type,
            "latest_quality_score": setup.get("quality_score", ""),
            "catalysts": catalysts,
            "status": _watchlist_status(latest_label),
            "still_fresh": "true" if latest_label in FRESH_LABELS else "false",
            "age_days": str(_age_days(first_seen, latest_seen or now)),
            "mention_count": setup.get("mention_count", ""),
        }
    return sorted(memory.values(), key=lambda row: row["ticker"])


def build_account_leaderboard(signals: list[dict], setup_rows: list[dict]) -> list[dict]:
    setup_by_ticker = {row["ticker"]: row for row in setup_rows}
    setup_first = {row["ticker"]: (row.get("first_seen_at"), row.get("first_account")) for row in setup_rows}
    by_account: dict[str, list[dict]] = defaultdict(list)
    for signal in signals:
        account = signal.get("account", "")
        if account:
            by_account[account].append(signal)

    rows: list[dict] = []
    for account, account_signals in by_account.items():
        tickers = [row.get("ticker", "").upper() for row in account_signals if row.get("ticker")]
        distinct_tickers = sorted(set(tickers))
        weights = [_to_float(row.get("account_weight")) or 0.25 for row in account_signals]
        entry_count = sum(1 for row in account_signals if row.get("action") == "entry")
        first_count = 0
        quality_values = []
        for row in account_signals:
            ticker = row.get("ticker", "").upper()
            setup = setup_by_ticker.get(ticker)
            if setup:
                value = _to_float(setup.get("quality_score"))
                if value is not None:
                    quality_values.append(value)
            first_seen, first_account = setup_first.get(ticker, ("", ""))
            if first_account == account and row.get("tweet_created_at") == first_seen:
                first_count += 1
        avg_quality = mean(quality_values) if quality_values else 0.0
        avg_hype = _avg_float(row.get("hype_score") for row in account_signals)
        weighted_signal_score = sum(weights)
        score = weighted_signal_score + entry_count * 0.75 + first_count * 1.5 + avg_quality * 0.25 - avg_hype * 2
        top_tickers = [ticker for ticker, _ in Counter(tickers).most_common(8)]
        tiers = Counter(row.get("account_tier", "unknown") for row in account_signals)
        rows.append(
            {
                "account": account,
                "account_tier": tiers.most_common(1)[0][0] if tiers else "unknown",
                "mention_count": str(len(account_signals)),
                "distinct_ticker_count": str(len(distinct_tickers)),
                "entry_count": str(entry_count),
                "first_mention_count": str(first_count),
                "weighted_signal_score": _fmt(weighted_signal_score),
                "avg_ticker_quality_score": _fmt(avg_quality),
                "avg_hype_score": _fmt(avg_hype),
                "leaderboard_score": _fmt(score),
                "top_tickers": ";".join(top_tickers),
            }
        )
    rows.sort(key=lambda row: float(row["leaderboard_score"]), reverse=True)
    return rows


def _summarize_signals(signals: list[dict]) -> dict:
    sorted_signals = sorted(signals, key=lambda row: row.get("tweet_created_at", ""))
    account_weights: dict[str, float] = {}
    for row in sorted_signals:
        account = row.get("account", "")
        if not account:
            continue
        account_weights[account] = max(account_weights.get(account, 0.0), _to_float(row.get("account_weight")) or 0.25)
    actions = Counter(row.get("action", "mention") for row in sorted_signals)
    catalysts = sorted(
        {
            catalyst
            for row in sorted_signals
            for catalyst in (row.get("catalysts") or "").split(";")
            if catalyst
        }
    )
    news = sorted({CATALYST_TO_NEWS.get(catalyst, "sector") for catalyst in catalysts}) or ["social_only"]
    top_accounts = [account for account, _ in Counter(row.get("account", "") for row in sorted_signals).most_common(6) if account]
    present_lower = {account.lower() for account in account_weights}
    cluster_overlap = len(CLUSTER_CORE & present_lower)
    cluster_confirmed = bool(CLUSTER_CONFIRM & present_lower)
    return {
        "mention_count": len(sorted_signals),
        "distinct_account_count": len(account_weights),
        "source_score": sum(account_weights.values()),
        "entry_count": actions["entry"],
        "watch_count": actions["watch"],
        "exit_count": actions["exit"],
        "short_count": actions["short"],
        "avg_hype_score": _avg_float(row.get("hype_score") for row in sorted_signals),
        "catalysts": catalysts,
        "news_confirmation": news,
        "first_seen_at": sorted_signals[0].get("tweet_created_at", "") if sorted_signals else "",
        "latest_mention_at": sorted_signals[-1].get("tweet_created_at", "") if sorted_signals else "",
        "first_account": sorted_signals[0].get("account", "") if sorted_signals else "",
        "top_accounts": top_accounts,
        "cluster_overlap": cluster_overlap,
        "cluster_confirmed": cluster_confirmed,
        "co_mentions": [t for t, _ in Counter(
            t.strip()
            for row in sorted_signals
            for t in (row.get("co_tickers") or "").split(",")
            if t.strip()
        ).most_common(5)],
    }


def _price_context(rows: list[dict]) -> dict:
    rows = sorted(rows, key=lambda row: row.get("date", ""))
    if not rows:
        return _blank_price_context()
    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else None
    close = _to_float(latest.get("close"))
    if close is None:
        return _blank_price_context()

    last_20 = rows[-20:] if len(rows) >= 20 else rows
    high_20 = max((_to_float(row.get("high")) or close) for row in last_20)
    low_20 = min((_to_float(row.get("low")) or close) for row in last_20)
    prior_volumes = [_to_float(row.get("volume")) for row in rows[-21:-1]]
    prior_volumes = [value for value in prior_volumes if value and value > 0]
    current_volume = _to_float(latest.get("volume"))

    return {
        "price_data_available": "true",
        "price_date": latest.get("date", ""),
        "prior_ret_1d": _fmt(_prior_return(rows, 1)),
        "prior_ret_5d": _fmt(_prior_return(rows, 5)),
        "prior_ret_20d": _fmt(_prior_return(rows, 20)),
        "current_gap": _fmt(((_to_float(latest.get("open")) or close) / (_to_float(previous.get("close")) or close) - 1) if previous else None),
        "relative_volume": _fmt((current_volume / mean(prior_volumes)) if current_volume and prior_volumes else None),
        "distance_from_20d_high": _fmt(close / high_20 - 1 if high_20 else None),
        "max_drawdown_20d": _fmt(low_20 / high_20 - 1 if high_20 else None),
    }


def _label_setup(summary: dict, price: dict) -> tuple[str, str]:
    source_score = summary["source_score"]
    distinct_accounts = summary["distinct_account_count"]
    has_catalyst = bool(summary["catalysts"])
    avg_hype = summary["avg_hype_score"]
    has_negative = summary["exit_count"] > 0 or summary["short_count"] > 0
    p1 = _to_float(price.get("prior_ret_1d"))
    p5 = _to_float(price.get("prior_ret_5d"))
    p20 = _to_float(price.get("prior_ret_20d"))
    rel_volume = _to_float(price.get("relative_volume"))
    distance_high = _to_float(price.get("distance_from_20d_high"))
    price_available = price.get("price_data_available") == "true"
    near_high = distance_high is not None and distance_high >= -0.03

    # A name in a strong 20-day uptrend near its highs is a leader pulling back,
    # not a name to avoid — bearish chatter / a 5-day dip on it is usually noise.
    # (Backtest: avoid_wait winners had +35% r20 / −6% from high vs losers +8% / −11%.)
    strong_uptrend = (
        price_available and p20 is not None and p20 >= 0.15
        and distance_high is not None and distance_high >= -0.08
    )
    # fresh_watch only pays off when there's accumulation behind it — quiet names
    # (rel_volume < 1.2, flat) were the duds. Require volume/price confirmation.
    confirmed = (
        not price_available
        or (rel_volume is not None and rel_volume >= 1.2)
        or (p1 is not None and p1 > 0.0)
    )

    if has_negative and summary["entry_count"] == 0 and not strong_uptrend:
        return "avoid_wait", "negative or exit-heavy account chatter"
    if price_available and p5 is not None and p5 < -0.08 and not strong_uptrend:
        return "avoid_wait", "weak recent price action"
    if source_score <= 0.5 and distinct_accounts <= 1 and (not has_catalyst or avg_hype >= 0.5):
        return "noise", "low-quality or single-source social chatter"
    if price_available and ((p1 is not None and p1 > 0.10) or (p5 is not None and p5 > 0.25)):
        return "late_chase", "already moved too far over the 1D/5D window"
    if price_available and ((p5 is not None and p5 > 0.15) or (near_high and p5 is not None and p5 > 0.08)):
        return "extended", "near recent highs after a meaningful move"
    if price_available and p1 is not None and p1 > 0.03 and source_score >= 1.0 and has_catalyst:
        return "momentum_confirmed", "price action confirms quality chatter"
    if source_score >= 1.0 and has_catalyst and confirmed and (not price_available or ((p5 or 0.0) < 0.08 and not near_high)):
        return "fresh_watch", "quality chatter + volume/price confirmation before the move"
    if distinct_accounts >= 2 and source_score >= 1.25 and (not price_available or (p5 is None or 0.0 <= p5 <= 0.15)):
        return "building", "multiple quality accounts are converging"
    if has_negative and not strong_uptrend:
        return "avoid_wait", "mixed chatter includes exits or shorts"
    if strong_uptrend:
        return "extended", "strong uptrend near highs; bearish chatter overridden by trend"
    return "noise", "not enough quality, catalyst, or price confirmation"


def _quality_score(summary: dict, price: dict, label: str) -> tuple[float, float]:
    source_score = summary["source_score"]
    distinct_bonus = min(summary["distinct_account_count"], 5) * 0.35
    action_bonus = summary["entry_count"] * 0.45 + summary["watch_count"] * 0.25
    catalyst_bonus = min(len(summary["catalysts"]), 3) * 0.4
    p1 = _to_float(price.get("prior_ret_1d")) or 0.0
    p5 = _to_float(price.get("prior_ret_5d")) or 0.0
    price_bonus = 0.0
    if 0.0 <= p5 <= 0.15:
        price_bonus += 0.5
    if 0.0 <= p1 <= 0.08:
        price_bonus += 0.25
    penalty = summary["avg_hype_score"] * 1.5 + summary["exit_count"] * 0.7 + summary["short_count"] * 0.7
    if label in CHASE_LABELS:
        penalty += 1.0
    if label == "noise":
        penalty += 1.25
    if price.get("price_data_available") != "true":
        penalty += 0.75
    # Cluster bonus: weighted overlap of the highest-performing account trio
    core_overlap = summary.get("cluster_overlap", 0)
    confirm_present = summary.get("cluster_confirmed", False)
    if core_overlap >= 3:
        cluster_bonus = 2.5
    elif core_overlap >= 2:
        cluster_bonus = 1.25
    else:
        cluster_bonus = 0.0
    if confirm_present and core_overlap >= 1:
        cluster_bonus += 1.0
    base = source_score + distinct_bonus + action_bonus + catalyst_bonus + price_bonus - penalty
    return max(0.0, base + cluster_bonus), cluster_bonus


def _warnings(ticker: str, summary: dict, price: dict, label: str) -> list[str]:
    warnings: list[str] = []
    if price.get("price_data_available") != "true":
        warnings.append("unpriced")
    asset = asset_warning(ticker)
    if asset:
        warnings.append(asset)
    if summary["distinct_account_count"] <= 1:
        warnings.append("single_source")
    if not summary["catalysts"]:
        warnings.append("social_only")
    if summary["avg_hype_score"] >= 0.5:
        warnings.append("high_hype")
    if label in CHASE_LABELS:
        warnings.append("chase_risk")
    if summary["exit_count"] or summary["short_count"]:
        warnings.append("negative_chatter")
    return warnings


def _confidence_label(summary: dict, price: dict, warnings: list[str]) -> str:
    if "unpriced" in warnings or "asset_ambiguous" in warnings:
        return "low"
    if summary["source_score"] >= 2.0 and summary["distinct_account_count"] >= 3 and price.get("price_data_available") == "true":
        return "high"
    if summary["source_score"] >= 1.0 and summary["distinct_account_count"] >= 2:
        return "medium"
    return "low"


def _actionability_rank(label: str, price: dict, warnings: list[str]) -> int:
    base = {
        "fresh_watch": 90,
        "building": 80,
        "momentum_confirmed": 70,
        "extended": 45,
        "late_chase": 35,
        "avoid_wait": 20,
        "noise": 10,
    }[label]
    if "unpriced" in warnings:
        base -= 25
    if "single_source" in warnings:
        base -= 10
    if "chase_risk" in warnings:
        base -= 10
    if price.get("price_data_available") == "true" and _to_float(price.get("relative_volume")) and (_to_float(price.get("relative_volume")) or 0) >= 1.5:
        base += 5
    return max(0, min(100, base))


def _actionability(label: str) -> str:
    return {
        "fresh_watch": "watch for confirmation before the move gets crowded",
        "building": "watch for chart confirmation and expanding volume",
        "momentum_confirmed": "momentum is confirmed; use pullbacks or tight levels",
        "extended": "interesting theme, but avoid chasing the current move",
        "late_chase": "already ran; wait for reset",
        "avoid_wait": "avoid or wait until the setup repairs",
        "noise": "low-confidence signal; use only as sentiment color",
    }[label]


def _watchlist_status(label: str) -> str:
    if label in ACTIVE_LABELS:
        return "active"
    if label in CHASE_LABELS:
        return "crowded"
    if label == "avoid_wait":
        return "wait"
    return "noise"


def _max_iso(left: str, right: str) -> str:
    values = [value for value in (left, right) if value]
    return max(values) if values else ""


def _age_days(first_seen: str, latest_seen: str) -> int:
    try:
        first = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
        latest = datetime.fromisoformat(latest_seen.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, (latest - first).days)


def _prices_by_ticker(prices: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in prices:
        ticker = (row.get("ticker") or "").upper()
        if ticker:
            grouped[ticker].append(row)
    return grouped


def _prior_return(rows: list[dict], days: int) -> float | None:
    if len(rows) <= days:
        return None
    close = _to_float(rows[-1].get("close"))
    prior = _to_float(rows[-1 - days].get("close"))
    if close is None or not prior:
        return None
    return close / prior - 1


def _blank_price_context() -> dict:
    return {
        "price_data_available": "false",
        "price_date": "",
        "prior_ret_1d": "",
        "prior_ret_5d": "",
        "prior_ret_20d": "",
        "current_gap": "",
        "relative_volume": "",
        "distance_from_20d_high": "",
        "max_drawdown_20d": "",
    }


def _merge_tokens(left: str, right: str) -> str:
    tokens = sorted({token for value in (left, right) for token in value.split(";") if token})
    return ";".join(tokens)


def _avg_float(values) -> float:
    clean = [_to_float(value) for value in values]
    clean = [value for value in clean if value is not None]
    return mean(clean) if clean else 0.0


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"
