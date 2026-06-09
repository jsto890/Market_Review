#!/usr/bin/env zsh
# Daily market pipeline — run by launchd at 08:00 local time.
# Fetches fresh X posts, rebuilds setups, runs Argus 52-agent analysis.
set -euo pipefail

set +e; source /Users/josephstorey/.zprofile 2>/dev/null; set -euo pipefail  # loads X_BEARER_TOKEN (ignore unrelated profile errors e.g. missing fsl.sh)

PYTHON=/Users/josephstorey/anaconda3/bin/python
ARGUS_PYTHON=/Users/josephstorey/Market_Analyse/argus/.venv/bin/python
MARKET_REVIEW=/Users/josephstorey/Market_Review
MARKET_ANALYSE=/Users/josephstorey/Market_Analyse

LOG_DIR="$MARKET_REVIEW/logs"
LOG="$LOG_DIR/daily_$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR"
exec >> "$LOG" 2>&1

echo "===== Market Review daily run — $(date) ====="

cd "$MARKET_REVIEW"
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli fetch-x --since-last --approve-x-cost
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli extract-signals
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli fetch-prices \
    --start "$(TZ=America/New_York date -v-30d +%Y-%m-%d)" \
    --end   "$(TZ=America/New_York date -v+1d +%Y-%m-%d)"
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli classify-setups
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli update-watchlist
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli memo --since-last

echo "----- Broad cashtag discovery -----"
cd "$MARKET_REVIEW"
DISCOVERED=$(PYTHONPATH=src "$PYTHON" -c "
from datetime import datetime, timezone, timedelta
from pathlib import Path
from stock_chatter.x_api import fetch_trending_cashtag_posts
from stock_chatter.discovery import select_candidates

end = datetime.now(timezone.utc) - timedelta(seconds=15)
start = end - timedelta(hours=10)
posts = fetch_trending_cashtag_posts(start_time=start, end_time=end, max_pages=3, approve_cost=True)
tickers = select_candidates(posts, memory_path=Path('reports/watchlist_memory.csv'))
print(','.join(tickers))
" 2>/dev/null || echo "")
echo "Discovered: ${DISCOVERED:-none}"

echo "----- Sentiment × Technical bridge -----"
cd "$MARKET_ANALYSE/argus"
FIXED_TICKERS="SMR,CCJ,UEC,LEU,OKLO,UUUU,DNN,NNE,IONQ,RGTI,QBTS,QUBT,RKLB,ASTS,LUNR,RDW,BKSY"
EXTRA="${FIXED_TICKERS}${DISCOVERED:+,$DISCOVERED}"
MARKET_REVIEW_REPORT="$MARKET_REVIEW/reports/ticker_setups.csv" \
"$ARGUS_PYTHON" ../sentiment_bridge.py \
    --min-quality 5 \
    --include-late-chase \
    --extra-tickers "$EXTRA" \
    --out ../reports/

echo "----- Copying reports to Obsidian -----"
OBSIDIAN_DIR="/Users/josephstorey/Documents/Obsidian Vault/Finance/Market Reports"
DATE_TAG="$(date +%Y-%m-%d)"
cp "$MARKET_REVIEW/reports/latest_memo.md"       "$OBSIDIAN_DIR/$DATE_TAG Twitter Memo.md"
cp "$MARKET_ANALYSE/reports/bridge_latest.md"    "$OBSIDIAN_DIR/$DATE_TAG Sentiment + Technicals.md"

echo "===== Done — $(date) ====="
