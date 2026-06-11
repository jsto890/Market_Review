#!/usr/bin/env zsh
# Wrapper — implementation lives in scripts/refresh_bridge.sh.
exec "$(dirname "$0")/scripts/refresh_bridge.sh" "$@"
