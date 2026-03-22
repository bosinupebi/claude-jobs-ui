#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Verify Python 3
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 not found. Install it from https://python.org" >&2
  exit 1
fi

# Install Flask if missing
if ! python3 -c "import flask" 2>/dev/null; then
  echo "Installing Flask..."
  pip3 install flask --break-system-packages 2>/dev/null || pip3 install flask
fi

PORT=5050

# Check if port is already in use; try 5051 as fallback
if lsof -i ":$PORT" -t &>/dev/null; then
  PORT=5051
  if lsof -i ":$PORT" -t &>/dev/null; then
    echo "Error: Ports 5050 and 5051 are both in use. Close the existing server and try again." >&2
    exit 1
  fi
fi

echo "Starting Job Search UI on http://localhost:$PORT"
echo "Press Ctrl+C to stop."
echo ""

# Open browser after Flask has time to bind
(sleep 1.5 && open "http://localhost:$PORT") &

python3 app.py --port "$PORT"
