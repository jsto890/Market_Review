# Market_Review — Project Context

## Overview
Local Python tooling for a daily US stock-chatter memo. Monitors tiered X/Twitter accounts (with explicit X API cost gating), aggregates sentiment, and produces a daily report. Also pulls market data via yfinance. Feeds the Argus technicals pipeline in `Market_Analyse`.

## Agent Shortlist
Curated from `~/.claude/agents/` (140 global agents, available in every project automatically — no copy needed). Spawn these proactively; add more as the work demands.

**Primary**
- `python-pro` — pipeline code, typing, API clients, pandas
- `data-engineer` — ingestion, scheduling (`run_daily.sh`), data flow into reports
- `nlp-engineer` — sentiment scoring, ticker/entity extraction from posts
- `data-analyst` — chatter aggregation, tier summaries, report metrics
- `code-reviewer` — correctness, cost-gating safety, secret handling

**Situational**
- `ai-engineer` — if memo generation/summarisation uses an LLM
- `research-analyst` — methodology for sentiment tiers and account weighting
- `test-automator` — coverage for parsing/aggregation logic
- `debugger` — feed/API failures, missing tickers
