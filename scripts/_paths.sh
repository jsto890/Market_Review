# Shared paths for Market_Review shell scripts. Source from scripts/*.sh.
MARKET_REVIEW="${MARKET_REVIEW:-$(cd "$(dirname "${(%):-%x}")/.." && pwd)}"
MARKET_ANALYSE="${MARKET_ANALYSE:-$(cd "$MARKET_REVIEW/../Market_Analyse" 2>/dev/null && pwd)}"
PYTHON="${PYTHON:-${HOME}/anaconda3/bin/python}"
ARGUS_PYTHON="${ARGUS_PYTHON:-${MARKET_ANALYSE}/argus/.venv/bin/python}"
OBSIDIAN_DIR="${OBSIDIAN_DIR:-${HOME}/Documents/Obsidian Vault/Finance/Market Reports}"
