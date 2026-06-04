from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone


def render_memo(
    *,
    signals: list[dict],
    scores: list[dict],
    x_skipped: bool,
    setups: list[dict] | None = None,
    leaderboard: list[dict] | None = None,
    watchlist: list[dict] | None = None,
    backtest: list[dict] | None = None,
    memo_type: str = "US Stock Chatter Memo",
    generated_at: datetime | None = None,
    since: str | None = None,
) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    account_status = {row.get("account"): row for row in scores}
    ticker_counts = Counter(row.get("ticker") for row in signals if row.get("ticker"))
    recent = signals[-80:]
    catalyst_by_ticker: dict[str, set[str]] = defaultdict(set)
    accounts_by_ticker: dict[str, set[str]] = defaultdict(set)
    for row in recent:
        ticker = row.get("ticker")
        if not ticker:
            continue
        accounts_by_ticker[ticker].add(row.get("account", ""))
        for catalyst in (row.get("catalysts") or "").split(";"):
            if catalyst:
                catalyst_by_ticker[ticker].add(catalyst)

    lines = [
        f"# {memo_type}",
        "",
        f"Generated: {generated_at.isoformat()}",
    ]
    if since:
        lines.append(f"Signal window: since {since}")
    if setups is not None:
        _render_data_freshness(lines, signals, setups, x_skipped)
        _render_action_queue(lines, setups)
        _render_changed(lines, watchlist or [])
        _render_blocked(lines, setups)
        _render_setup_sections(lines, setups)
        _render_leaderboard(lines, leaderboard or [])
        _render_backtest(lines, backtest or [])
        _render_theme_map(lines, setups)
        lines.extend(["", "## X Coverage"])
        if x_skipped:
            lines.append("- X API coverage skipped for this run because per-run paid API approval was not supplied.")
        else:
            lines.append("- X account signals are included from the local fetched dataset.")
        lines.extend(["", "## Actionability Notes"])
        lines.append("- Treat setup labels as decision support, not automatic entries.")
        lines.append("- Fresh and building names still need chart/news confirmation.")
        lines.append("- Late-chase and extended names may remain good themes but need a reset.")
        return "\n".join(lines) + "\n"

    lines.extend(["", "## Top Talked-About Stocks"])
    if ticker_counts:
        for ticker, count in ticker_counts.most_common(10):
            catalysts = ", ".join(sorted(catalyst_by_ticker[ticker])) or "no explicit catalyst tagged"
            accounts = ", ".join(sorted(filter(None, accounts_by_ticker[ticker]))[:5])
            lines.append(f"- ${ticker}: {count} mention(s). Catalysts: {catalysts}. Accounts: {accounts or 'unknown'}.")
    else:
        lines.append("- No local ticker mentions available yet.")

    lines.extend(["", "## Reliable Account Chatter"])
    if x_skipped:
        lines.append("- X API coverage skipped for this run because per-run paid API approval was not supplied.")
    trusted = [row for row in scores if row.get("status") == "trusted"]
    pending = [row for row in scores if row.get("status") != "trusted"]
    if trusted:
        for row in trusted[:8]:
            lines.append(
                f"- {row['account']}: trust score {row['trust_score']}, "
                f"{row['complete_20d_count']} completed 20D calls, hit rate {row['hit_rate_20d'] or 'n/a'}."
            )
    elif pending:
        lines.append("- No account has enough completed forward-return history to be marked trusted yet.")

    lines.extend(["", "## News That Can Move Stocks"])
    lines.append("- Add confirmed earnings, filings, analyst actions, macro/rates, commodities, and sector ETF moves here during live memo generation.")

    lines.extend(["", "## Areas To Watch"])
    sector_tags = Counter()
    for row in recent:
        for tag in (row.get("catalysts") or "").split(";"):
            if tag:
                sector_tags[tag] += 1
    if sector_tags:
        for tag, count in sector_tags.most_common(6):
            lines.append(f"- {tag.replace('_', ' ').title()}: {count} tagged mention(s).")
    else:
        lines.append("- No dominant local theme tagged yet.")

    lines.extend(["", "## Actionability Notes"])
    lines.append("- Treat new ticker mentions as prompts for chart/news confirmation, not automatic entries.")
    lines.append("- Prefer fresh mentions before a large move; penalize crowded names that have already run.")
    lines.append("- Forward-return trust scores build over time as 1D/5D/20D/60D windows complete.")
    return "\n".join(lines) + "\n"


def _render_setup_sections(lines: list[str], setups: list[dict]) -> None:
    sections = [
        ("Fresh Watch", {"fresh_watch", "building"}),
        ("Momentum Confirmed", {"momentum_confirmed"}),
        ("Already Ran / Chase Risk", {"extended", "late_chase"}),
        ("Speculative / Noise", {"noise"}),
        ("Avoid / Wait", {"avoid_wait"}),
    ]
    for title, labels in sections:
        lines.extend(["", f"## {title}"])
        rows = [row for row in setups if row.get("setup_label") in labels]
        if not rows:
            lines.append("- None.")
            continue
        for row in rows[:10]:
            lines.append(_setup_line(row))


def _render_data_freshness(lines: list[str], signals: list[dict], setups: list[dict], x_skipped: bool) -> None:
    latest_post = max((row.get("tweet_created_at", "") for row in signals), default="")
    latest_price = max((row.get("price_date", "") for row in setups if row.get("price_date")), default="")
    unpriced = sum(1 for row in setups if row.get("price_data_available") != "true")
    pending = "yes" if x_skipped else "no"
    lines.extend(["", "## Data Freshness"])
    lines.append(f"- Latest saved X post: {latest_post or 'n/a'}.")
    lines.append(f"- Latest price context: {latest_price or 'n/a'}.")
    lines.append(f"- Unpriced setup tickers: {unpriced}.")
    lines.append(f"- X skipped this run: {pending}.")


def _render_action_queue(lines: list[str], setups: list[dict]) -> None:
    candidates = [
        row
        for row in setups
        if row.get("setup_label") in {"fresh_watch", "building", "momentum_confirmed"}
        and row.get("price_data_available") == "true"
        and "chase_risk" not in (row.get("warnings") or "")
    ]
    candidates.sort(key=lambda row: (int(row.get("actionability_rank") or 0), _float(row.get("quality_score"))), reverse=True)
    lines.extend(["", "## Action Queue"])
    if not candidates:
        lines.append("- No priced fresh/momentum candidates cleared the basic warning filters.")
        return
    for row in candidates[:5]:
        warnings = row.get("warnings") or "none"
        lines.append(
            f"- ${row.get('ticker')}: {row.get('setup_label')} ({row.get('confidence_label', 'unknown')} confidence). "
            f"Why now: {row.get('reason')}. Confirm: price/news/volume before action. "
            f"Invalid if: setup loses price confirmation or warnings increase. Warnings: {warnings}."
        )


def _render_changed(lines: list[str], watchlist: list[dict]) -> None:
    changed = [row for row in watchlist if row.get("label_changed") == "true"]
    lines.extend(["", "## Changed Since Last Run"])
    if not changed:
        lines.append("- No setup label changes recorded in watchlist memory.")
        return
    for row in changed[:8]:
        lines.append(
            f"- ${row.get('ticker')}: {row.get('previous_setup_label') or 'unknown'} -> "
            f"{row.get('latest_setup_label')} ({row.get('status')})."
        )


def _render_blocked(lines: list[str], setups: list[dict]) -> None:
    blocked = [row for row in setups if any(token in (row.get("warnings") or "") for token in ("unpriced", "asset_ambiguous", "single_source"))]
    lines.extend(["", "## Needs Confirmation / Blocked"])
    if not blocked:
        lines.append("- No major data-quality blockers.")
        return
    for row in blocked[:8]:
        lines.append(f"- ${row.get('ticker')}: {row.get('setup_label')} blocked by {row.get('warnings') or 'unknown warnings'}.")


def _render_leaderboard(lines: list[str], leaderboard: list[dict]) -> None:
    lines.extend(["", "## Account Leaderboard"])
    if not leaderboard:
        lines.append("- No account leaderboard available yet.")
        return
    for row in leaderboard[:8]:
        lines.append(
            f"- {row.get('account')}: score {row.get('leaderboard_score')}, "
            f"{row.get('mention_count')} mentions, {row.get('distinct_ticker_count')} tickers, "
            f"top tickers {row.get('top_tickers') or 'n/a'}."
        )


def _render_backtest(lines: list[str], backtest: list[dict]) -> None:
    lines.extend(["", "## Account Trust"])
    if not backtest:
        lines.append("- No account backtest rows available yet.")
        return
    for row in backtest[:8]:
        lines.append(
            f"- {row.get('account')}: {row.get('trust_label')} | evidence {row.get('evidence_status')} | "
            f"1D hit {_pct(row.get('hit_rate_1d')) or 'n/a'} on {row.get('complete_1d_count')} events, "
            f"5D/20D complete {row.get('complete_5d_count')}/{row.get('complete_20d_count')}."
        )


def _render_theme_map(lines: list[str], setups: list[dict]) -> None:
    lines.extend(["", "## Theme Map"])
    catalyst_counts = Counter()
    news_counts = Counter()
    for row in setups:
        for catalyst in (row.get("catalysts") or "").split(";"):
            if catalyst:
                catalyst_counts[catalyst] += 1
        for news in (row.get("news_confirmation") or "").split(";"):
            if news:
                news_counts[news] += 1
    if not catalyst_counts and not news_counts:
        lines.append("- No dominant theme tagged yet.")
        return
    for catalyst, count in catalyst_counts.most_common(8):
        lines.append(f"- {catalyst.replace('_', ' ').title()}: {count} ticker(s).")
    if news_counts:
        lines.append(f"- Catalyst type mix: {_counter_summary(news_counts)}.")


def _setup_line(row: dict) -> str:
    catalysts = row.get("catalysts") or "social_only"
    accounts = row.get("top_accounts") or "unknown"
    price_bits = []
    for label, key in (("1D", "prior_ret_1d"), ("5D", "prior_ret_5d"), ("20D", "prior_ret_20d")):
        value = _pct(row.get(key))
        if value:
            price_bits.append(f"{label} {value}")
    price = ", ".join(price_bits) if price_bits else "price n/a"
    return (
        f"- ${row.get('ticker')}: {row.get('setup_label')} | score {_score(row.get('quality_score'))} | "
        f"{row.get('mention_count')} mentions/{row.get('distinct_account_count')} accounts | "
        f"{price} | catalysts {catalysts} | accounts {accounts} | {row.get('reason')}."
    )


def _pct(value: str | None) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return ""


def _score(value: str | None) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "n/a"


def _float(value: str | None) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _counter_summary(counter: Counter) -> str:
    return ", ".join(f"{key} {value}" for key, value in counter.most_common(6))
