#!/bin/bash

# START_SERVER.sh - Guaranteed to use .venv Python with reportlab
# Usage: bash START_SERVER.sh

set -e

SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SERVER_DIR}/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: .venv not found at $SERVER_DIR/.venv"
    echo "Please run: python -m venv .venv"
    exit 1
fi

echo "Starting server with Python: $VENV_PYTHON"
$VENV_PYTHON --version

cd "$SERVER_DIR"

# Kill any existing server processes for THIS project only
pkill -f "uvicorn app.main:app.*--port 8000" || true
sleep 1

# Start uvicorn with explicit .venv Python
exec $VENV_PYTHON -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
