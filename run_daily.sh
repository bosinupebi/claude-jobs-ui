#!/usr/bin/env bash
# Wrapper used by launchd/cron to run the daily job-search pipeline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV_FILE="$SCRIPT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
fi

# launchd starts with a small PATH, so include common Homebrew, nvm, and user bins.
export PATH="$HOME/.nvm/versions/node/v23.1.0/bin:/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

PYTHON="$(command -v python3 || true)"
if [[ -z "$PYTHON" ]]; then
  echo "[ERROR] python3 not found in PATH" >&2
  exit 2
fi

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') job_search_daily starting ===" >> "$LOG_DIR/runner.log"

"$PYTHON" "$SCRIPT_DIR/job_search_daily.py" "$@"
EXIT_CODE=$?

echo "=== $(date '+%Y-%m-%d %H:%M:%S') exit code: $EXIT_CODE ===" >> "$LOG_DIR/runner.log"
exit "$EXIT_CODE"
