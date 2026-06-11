#!/usr/bin/env zsh
# Refresh Argus technical scores on latest EOD prices + update bridge report.
# Run after US market close — launchd fires at 06:15 AEST (= 16:15 ET).
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
source "$SCRIPT_DIR/_paths.sh"
source "${HOME}/.zprofile"

LOG_DIR="$MARKET_REVIEW/logs"
LOG="$LOG_DIR/bridge_refresh_$(date +%Y%m%d_%H%M).log"
mkdir -p "$LOG_DIR"
exec >> "$LOG" 2>&1

echo "===== Bridge refresh — $(date) ====="

cd "$MARKET_REVIEW"
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli fetch-prices \
    --start "$(TZ=America/New_York date -v-30d +%Y-%m-%d)" \
    --end   "$(TZ=America/New_York date -v+1d +%Y-%m-%d)"
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli classify-setups
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli memo --since-last

echo "----- Sentiment × Technical bridge -----"
cd "$MARKET_ANALYSE/argus"
MARKET_REVIEW_REPORT="$MARKET_REVIEW/reports/ticker_setups.csv" \
"$ARGUS_PYTHON" ../sentiment_bridge.py \
    --min-quality 5 \
    --extra-tickers "SMR,CCJ,UEC,LEU,OKLO,UUUU,DNN,NNE,IONQ,RGTI,QBTS,QUBT,RKLB,ASTS,LUNR,RDW,BKSY" \
    --out ../reports/

echo "----- Copying to Obsidian -----"
DATE_TAG="$(date +%Y-%m-%d)"
cp "$MARKET_ANALYSE/reports/bridge_latest.md" "$OBSIDIAN_DIR/$DATE_TAG Daily Report.md"

echo "===== Done — $(date) ====="
