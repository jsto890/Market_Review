#!/usr/bin/env zsh
# Wrapper — implementation lives in scripts/run_daily.sh (launchd entrypoint).
exec "$(dirname "$0")/scripts/run_daily.sh" "$@"
