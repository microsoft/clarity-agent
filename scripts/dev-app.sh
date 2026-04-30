#!/usr/bin/env bash
#
# Launch the Tauri app in developer mode, using the repo's .env file
# and data directory instead of the platform default.
#
# Usage:
#   scripts/dev-app.sh                # launch the last build
#   scripts/dev-app.sh --build        # rebuild first, then launch
#
# This sets CLARITY_DATA_DIR to the repo root so the sidecar picks up
# the .env file sitting alongside clarity.py.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "${1:-}" == "--build" ]]; then
    uv run python "$REPO_ROOT/clarity.py" install
fi

APP="$REPO_ROOT/dist/Clarity.app"
BINARY="$APP/Contents/MacOS/clarity"

if [[ ! -f "$BINARY" ]]; then
    echo "No app build found at $APP"
    echo "Run 'clarity install' first, or use 'scripts/dev-app.sh --build'"
    exit 1
fi

export CLARITY_DATA_DIR="$REPO_ROOT"
echo "Using .env from: $REPO_ROOT/.env"
echo "Launching Clarity (dev mode)..."
exec "$BINARY"
