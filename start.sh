#!/usr/bin/env bash
# MarketReplay — Startup Script
# Run from the project root: bash start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
PORT="${PORT:-8000}"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║       MarketReplay Simulator         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
  echo "  ✗ Python not found. Install Python 3.9+ first."
  exit 1
fi

PYTHON=$(command -v python3 || command -v python)
echo "  ✓ Python: $($PYTHON --version)"

# Check / install dependencies
cd "$BACKEND_DIR"
if ! $PYTHON -c "import fastapi" &>/dev/null; then
  echo "  → Installing dependencies..."
  $PYTHON -m pip install -r requirements.txt -q
fi
echo "  ✓ Dependencies OK"

# Start server
echo ""
echo "  → Starting server on http://localhost:$PORT"
echo "  → Press Ctrl+C to stop"
echo ""

$PYTHON -m uvicorn main:app --reload --port "$PORT" --host 0.0.0.0