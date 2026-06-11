#!/usr/bin/env zsh
# Daily market pipeline — run by launchd at 08:00 local time.
# Fetches fresh X posts, rebuilds setups, runs Argus bridge analysis.
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/_paths.sh"

set +e; source "${HOME}/.zprofile" 2>/dev/null; set -euo pipefail

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
    --extra-tickers "$EXTRA" \
    --out ../reports/

echo "----- Copying reports to Obsidian -----"
DATE_TAG="$(date +%Y-%m-%d)"
cp "$MARKET_ANALYSE/reports/bridge_latest.md" "$OBSIDIAN_DIR/$DATE_TAG Daily Report.md"

echo "----- Ingesting bridge CSVs into dashboard DB -----"
mkdir -p "$MARKET_ANALYSE/logs"
(cd "$MARKET_ANALYSE/dashboard" && /opt/homebrew/bin/npm run ingest) \
  >> "$MARKET_ANALYSE/logs/ingest.log" 2>&1 || echo "ingest failed"

if [ "$(date +%d)" = "01" ]; then
  echo "----- Monthly label-efficacy backtest -----"
  cd "$MARKET_ANALYSE"
  "$ARGUS_PYTHON" tools/label_efficacy.py || echo "label_efficacy failed (non-fatal)"
fi

echo "===== Done — $(date) ====="
