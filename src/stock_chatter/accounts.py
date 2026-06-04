from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    handle: str
    tier: str
    purpose: str
    score_weight: float


ACCOUNTS: tuple[Account, ...] = (
    Account("@core_alpha_01", "core_alpha", "Small cap, sector rotation, short term and swing ideas", 1.0),
    Account("@core_alpha_02", "core_alpha", "Long-term thematic small/mid-cap research", 1.0),
    Account("@core_alpha_03", "core_alpha", "AI infrastructure, memory, data center, Asian tech", 1.0),
    Account("@core_alpha_04", "core_alpha", "Semis, memory, AI hardware supply chain", 1.0),
    Account("@core_alpha_05", "core_alpha", "Momentum growth and disruptive stock swings", 1.0),
    Account("@swing_01", "swing_watchlist", "Swing trading and thematic technical setups", 0.75),
    # Promoted from 0.75 → 0.90: 100% 1D hit rate over 75 signals (2-month backtest)
    Account("@swing_02", "swing_watchlist", "Small cap growth, technical levels, oversold setups", 0.90),
    # Promoted from 0.75 → 1.0: 90% 1D hit rate, +6.4% avg return over 17 calls (2-month backtest)
    Account("@swing_03", "swing_watchlist", "High beta growth, quantum, space, AI names", 1.0),
    Account("@swing_04", "swing_watchlist", "Turnaround and asymmetric small caps", 0.75),
    Account("@swing_05", "swing_watchlist", "Asymmetric investor; AI infrastructure, cloud, CPO names", 0.75),
    Account("@swing_06", "swing_watchlist", "Crypto/equity/options trader; AI infra, cloud, space", 0.70),
    Account("@swing_07", "swing_watchlist", "Defense/aerospace/space: KTOS RKLB RCAT AVAV", 0.70),
    Account("@swing_08", "swing_watchlist", "CPO/photonics specialist; LASR HIMX AOSL; asymmetric equity", 0.75),
    Account("@swing_09", "swing_watchlist", "Early-stage alpha; ONDS RCAT KTOS; niche small-cap ideas", 0.65),
    Account("@research_01", "long_term_research", "Options/market-structure flow; SPY QQQ index context", 0.55),
    Account("@research_02", "long_term_research", "Macro/sector context; SOX TIPS GME as sentiment indicators", 0.55),
    Account("@research_03", "long_term_research", "Fundamental long-term stock analysis", 0.55),
    Account("@research_04", "long_term_research", "Long-term thematic discovery", 0.55),
    Account("@research_05", "long_term_research", "Deep value mindset and long-term theses", 0.55),
    # weight: 0.35
    Account("@research_06", "long_term_research", "Concentrated long-term conviction ideas", 0.35),
    Account("@noise_01", "sentiment_noise", "Speculative small/mid-cap sentiment", 0.35),
    Account("@noise_02", "sentiment_noise", "High beta momentum sentiment", 0.35),
    # weight: 0.10
    Account("@noise_03", "sentiment_noise", "Position commentary and sentiment", 0.10),
    Account("@noise_04", "sentiment_noise", "Technical watchlists and short-term setups", 0.35),
    # weight: 0.10
    Account("@noise_05", "sentiment_noise", "Broad stock/crypto market timing context", 0.10),
)

# Accounts whose overlap on a ticker produces a cluster bonus in quality scoring.
# Core trio: highest hit-rate accounts by backtest. Confirm: strong corroborators.
CLUSTER_CORE: frozenset[str] = frozenset({
    "@core_alpha_01",
    "@swing_03",
    "@core_alpha_02",
})

CLUSTER_CONFIRM: frozenset[str] = frozenset({
    "@swing_02",
    "@core_alpha_05",
    "@swing_05",
    "@swing_08",
})


ACCOUNT_BY_HANDLE = {account.handle.lower(): account for account in ACCOUNTS}


def normalized_handle(handle: str) -> str:
    handle = handle.strip()
    if not handle:
        raise ValueError("handle cannot be empty")
    return handle if handle.startswith("@") else f"@{handle}"


def usernames() -> list[str]:
    return [account.handle.removeprefix("@") for account in ACCOUNTS]


def account_for_handle(handle: str) -> Account | None:
    return ACCOUNT_BY_HANDLE.get(normalized_handle(handle).lower())
