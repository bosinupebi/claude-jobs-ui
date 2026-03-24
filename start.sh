#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Verify Python 3
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 not found. Install it from https://python.org" >&2
  exit 1
fi

# Install Python dependencies
echo "Checking Python dependencies..."
pip3 install -r requirements.txt --break-system-packages -q 2>/dev/null || pip3 install -r requirements.txt -q

# Check for claude CLI (needed for document generation)
if ! command -v claude &>/dev/null; then
  echo "Warning: 'claude' CLI not found. Document generation will use the Anthropic SDK fallback." >&2
fi

# Check for md-to-pdf (needed for PDF generation)
if ! command -v md-to-pdf &>/dev/null; then
  echo "Warning: 'md-to-pdf' not found. Install it with: npm install -g md-to-pdf" >&2
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
