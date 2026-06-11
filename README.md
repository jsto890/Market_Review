# Stock Chatter Monitor

Local tooling for the daily US stock chatter memo.

## Disclaimer

This is an educational / portfolio project and is **not financial advice**.
Nothing here is a recommendation to buy or sell any security or instrument.
Any trading or order-execution functionality is provided for research and
demonstration only; use paper/simulated accounts unless you fully understand
the code and accept all risk. Backtested or past performance is not indicative
of future results. The author accepts no liability for any financial loss.

## Data & X Terms of Service

Data is fetched via the official X API v2 (Recent Search endpoint) under the
user's own developer credentials — no scraped tweet content is redistributed
in this repository (raw data is gitignored). The monitored-account list in
`src/stock_chatter/accounts.py` uses anonymised placeholder handles for
privacy; real account identities are not published.

## How ticker discovery works

Sentiment is **not** limited to the curated follow list. Three ingestion paths feed one pool:

| Path | What it does | CLI / entry point |
|------|----------------|-------------------|
| **Curated accounts** | Recent Search filtered to followed handles; trust tiers weight who said what | `fetch-x` → `extract-signals` |
| **Broad cashtag + phrase search** | Full public timeline scan (`stock`, `breakout`, `small cap`, `earnings`, … + `has:cashtags`); candidates bucketed into emerging small/mid-caps and running large-caps | `run_daily.sh` (calls `fetch_trending_cashtag_posts` + `discovery.select_candidates`) |
| **On-demand cashtag search** | `$TICKER` on the full timeline; flags which posters are in the curated list | `scripts/ticker_search.py SMR` |

All paths extract cashtags, tag catalysts from context phrases, classify setup labels, and write `reports/ticker_setups.csv`. The daily pipeline merges broad-discovery names into the Argus bridge via `--extra-tickers`.

It also supports:

- monitored X account tiers;
- explicit X API cost gating;
- cashtag extraction and catalyst tagging;
- setup warnings and actionability ranking;
- forward-return account trust files;
- unsupported ticker reporting;
- one-page memo and dashboard generation.

## Repository layout

```
Market_Review/
├── src/stock_chatter/     # package (cli, x_api, discovery, setups, …)
├── scripts/               # ops + ad-hoc utilities
│   ├── run_daily.sh       # full daily pipeline (+ Argus bridge)
│   ├── refresh_bridge.sh  # post-close price refresh + bridge
│   ├── ticker_search.py   # on-demand $TICKER X search
│   └── following_summary.py
├── run_daily.sh           # launchd entrypoint → scripts/run_daily.sh
├── data/                  # gitignored — raw posts, prices, signals
├── reports/               # gitignored — setups, watchlist, memo
└── logs/                  # gitignored — daily run logs
```

## Cost Rule

The CLI does not call X by default. It estimates request count and exits unless you pass:

```zsh
--approve-x-cost
```

Use that flag only after you have reviewed the estimated request count and accept any X pay-per-use cost risk.

## Setup

```zsh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,market]"
```

`X_BEARER_TOKEN` must be present in the environment before approved X fetches can run.

## Common Commands

Estimate X reads without making any X API call:

```zsh
PYTHONPATH=src python -m stock_chatter.cli estimate-x --since-hours 24
```

Fetch fresh account tweets only after approving X API cost risk:

```zsh
PYTHONPATH=src python -m stock_chatter.cli fetch-x --since-last --approve-x-cost
```

The default guard is `$1/day`, assuming `$0.005` per possible post read and a maximum of `100` posts per request page. Override only if you intentionally change the risk limit:

```zsh
PYTHONPATH=src python -m stock_chatter.cli fetch-x --since-last --approve-x-cost --daily-budget-usd 1 --assumed-post-read-cost-usd 0.005
```

The command sends `end_time` 15 seconds behind the current clock because X rejects Recent Search requests whose `end_time` is too close to request time.

For a targeted Recent Search slice, supply an explicit UTC window:

```zsh
PYTHONPATH=src python -m stock_chatter.cli fetch-x --start-time 2026-05-01T00:00:00Z --end-time 2026-05-02T00:00:00Z --max-pages 1 --approve-x-cost
```

Extract signals from saved X posts:

```zsh
PYTHONPATH=src python -m stock_chatter.cli extract-signals
```

Fetch price context for signal tickers:

```zsh
python -m pip install -e ".[market]"
PYTHONPATH=src python -m stock_chatter.cli fetch-prices --start 2026-04-01 --end 2026-05-07
```

This also writes `reports/unsupported_tickers.csv` for raw cashtags that did not resolve cleanly through yfinance.

Classify ticker setups from local signal and price files:

```zsh
PYTHONPATH=src python -m stock_chatter.cli classify-setups
PYTHONPATH=src python -m stock_chatter.cli update-watchlist
PYTHONPATH=src python -m stock_chatter.cli leaderboard
```

Backtest account trust from timestamped mentions and local prices:

```zsh
PYTHONPATH=src python -m stock_chatter.cli backtest
```

Trust labels remain `pending_forward_data` until enough 5D/20D forward-return windows complete. One-day returns are shown as provisional evidence, not account trust.

Repair the live X watermark from saved raw posts without making an API call:

```zsh
PYTHONPATH=src python -m stock_chatter.cli repair-state
```

Generate the latest memo from existing local data:

```zsh
PYTHONPATH=src python -m stock_chatter.cli memo --since-last --x-skipped
```

Generate the interactive HTML dashboard:

```zsh
PYTHONPATH=src python -m stock_chatter.cli dashboard
```

Run the local daily pipeline without calling X:

```zsh
PYTHONPATH=src python -m stock_chatter.cli daily-pipeline --x-skipped
```

On-demand cashtag search for a single ticker (full timeline, not just followed accounts):

```zsh
python scripts/ticker_search.py SMR --since-hours 48
```

Summarise recent posts from your following list (reads local cache, no API call):

```zsh
python scripts/following_summary.py --since-hours 72
```

Run the full daily driver (curated fetch + broad discovery + Argus bridge) — requires `X_BEARER_TOKEN` and `--approve-x-cost` on the X steps inside `scripts/run_daily.sh`:

```zsh
./run_daily.sh    # thin wrapper → scripts/run_daily.sh
```

Override paths via env vars: `MARKET_REVIEW`, `MARKET_ANALYSE`, `ARGUS_PYTHON`, `OBSIDIAN_DIR` (see `scripts/_paths.sh`).

Run tests:

```zsh
PYTHONPATH=src pytest
```

## Note on git history

This repository was developed privately and published as a clean snapshot. The single initial commit reflects a curated public release rather than the full development timeline.
