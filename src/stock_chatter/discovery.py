"""Bucket broad-scan cashtags into emerging small/mid-caps + running large-caps.

Raw mention volume surfaces megacaps that are already moving. For pre-catalyst
discovery we instead want small/mid-caps with rising account breadth, while still
keeping large-caps that are in a strong recent uptrend.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yfinance as yf

from .signals import rank_tickers_by_mention

US_EXCHANGES = frozenset(
    {"NYQ", "NMS", "NGM", "NCM", "ASE", "PCX", "BATS", "NYSE", "NASDAQ"}
)


def _load_known_ages(memory_path: Path | None) -> dict[str, float]:
    """Map ticker -> age_days from watchlist memory, for recency weighting."""
    ages: dict[str, float] = {}
    if not memory_path or not memory_path.exists():
        return ages
    with memory_path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            ticker = (row.get("ticker") or "").upper()
            if not ticker:
                continue
            try:
                ages[ticker] = float(row.get("age_days") or 0)
            except ValueError:
                ages[ticker] = 0.0
    return ages


def _us_equity_info(ticker: str) -> dict | None:
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return None
    if info.get("quoteType") != "EQUITY":
        return None
    if info.get("exchange", "") not in US_EXCHANGES:
        return None
    return info


def select_candidates(
    posts: list[dict],
    *,
    memory_path: Path | None = None,
    min_mentions: int = 3,
    min_unique_accounts: int = 4,
    smallmid_cap_min: float = 5e7,
    smallmid_cap_max: float = 10e9,
    n_smallmid: int = 12,
    n_largecap: int = 8,
    max_lookups: int = 60,
) -> list[str]:
    """Return discovered tickers: emerging small/mid-caps first, then running large-caps.

    - Small/mid ($50M–$10B): ranked by account breadth + a boost for names that are
      new or only recently first-seen in watchlist memory (the pre-catalyst signal).
    - Large-cap (>$10B): kept only if running well (price >= 50DMA >= 200DMA),
      ranked by mention volume.
    """
    ranked = rank_tickers_by_mention(
        posts, min_mentions=min_mentions, min_unique_accounts=min_unique_accounts
    )
    known_ages = _load_known_ages(memory_path)

    smallmid: list[tuple[float, str]] = []
    largecap: list[tuple[float, str]] = []

    for row in ranked[:max_lookups]:
        ticker = row["ticker"]
        info = _us_equity_info(ticker)
        if info is None:
            continue
        cap = info.get("marketCap") or 0
        breadth = row["unique_accounts"]

        if smallmid_cap_min <= cap <= smallmid_cap_max:
            age = known_ages.get(ticker)
            recency_boost = 3 if age is None else (2 if age <= 5 else 0)
            smallmid.append((breadth + recency_boost, ticker))
        elif cap > smallmid_cap_max:
            price = info.get("regularMarketPrice") or info.get("currentPrice") or 0
            dma50 = info.get("fiftyDayAverage") or 0
            dma200 = info.get("twoHundredDayAverage") or 0
            if price and dma50 and dma200 and price >= dma50 >= dma200:
                largecap.append((row["mention_count"], ticker))

    smallmid.sort(reverse=True)
    largecap.sort(reverse=True)

    out: list[str] = [t for _, t in smallmid[:n_smallmid]]
    for _, t in largecap[:n_largecap]:
        if t not in out:
            out.append(t)
    return out
