#!/usr/bin/env zsh
# Refresh Argus technical scores on latest EOD prices + update bridge report.
# Run after US market close — launchd fires at 06:15 AEST (= 16:15 ET).
set -euo pipefail

source /Users/josephstorey/.zprofile

PYTHON=/Users/josephstorey/anaconda3/bin/python
ARGUS_PYTHON=/Users/josephstorey/Market_Analyse/argus/.venv/bin/python
MARKET_REVIEW=/Users/josephstorey/Market_Review
MARKET_ANALYSE=/Users/josephstorey/Market_Analyse

LOG_DIR="$MARKET_REVIEW/logs"
LOG="$LOG_DIR/bridge_refresh_$(date +%Y%m%d_%H%M).log"
mkdir -p "$LOG_DIR"
exec >> "$LOG" 2>&1

echo "===== Bridge refresh — $(date) ====="

# Refresh prices for tickers in current setups
cd "$MARKET_REVIEW"
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli fetch-prices \
    --start "$(TZ=America/New_York date -v-30d +%Y-%m-%d)" \
    --end   "$(TZ=America/New_York date -v+1d +%Y-%m-%d)"
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli classify-setups
PYTHONPATH=src "$PYTHON" -m stock_chatter.cli memo --since-last

echo "----- Sentiment × Technical bridge -----"
cd "$MARKET_ANALYSE/argus"
"$ARGUS_PYTHON" ../sentiment_bridge.py \
    --min-quality 5 \
    --include-late-chase \
    --extra-tickers "SMR,CCJ,UEC,LEU,OKLO,UUUU,DNN,NNE,IONQ,RGTI,QBTS,QUBT,RKLB,ASTS,LUNR,RDW,BKSY" \
    --out ../reports/

echo "----- Copying to Obsidian -----"
OBSIDIAN_DIR="/Users/josephstorey/Documents/Obsidian Vault/Finance/Market Reports"
DATE_TAG="$(date +%Y-%m-%d)"
cp "$MARKET_REVIEW/reports/latest_memo.md"    "$OBSIDIAN_DIR/$DATE_TAG Twitter Memo.md"
cp "$MARKET_ANALYSE/reports/bridge_latest.md" "$OBSIDIAN_DIR/$DATE_TAG Sentiment + Technicals.md"

echo "===== Done — $(date) ====="
