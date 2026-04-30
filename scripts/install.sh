#!/bin/bash
# Clarity bootstrap installer — macOS and Linux.
#
# Downloads uv, clones the repo, then hands off to Python.
# Python handles everything else (platform detection, app assembly, shortcuts).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/microsoft/clarity-agent/main/scripts/install.sh | bash
#   curl -fsSL ... | bash -s -- --branch my-branch

set -euo pipefail

REPO="https://github.com/microsoft/clarity-agent.git"
BRANCH="main"

# Parse --branch <name> from args (remaining args are forwarded to Python).
FORWARD_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --branch) BRANCH="$2"; shift 2 ;;
        *) FORWARD_ARGS+=("$1"); shift ;;
    esac
done

WORK="$(mktemp -d)"

cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

# --- Download uv (needed to run Python before the venv exists) ---------------
UV="$WORK/uv"
ARCH="$(uname -m)"
OS="$(uname -s)"

if [ "$OS" = "Darwin" ]; then
    case "$ARCH" in
        arm64|aarch64) TARGET="aarch64-apple-darwin" ;;
        x86_64)        TARGET="x86_64-apple-darwin" ;;
        *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
else
    case "$ARCH" in
        x86_64)        TARGET="x86_64-unknown-linux-gnu" ;;
        aarch64|arm64) TARGET="aarch64-unknown-linux-gnu" ;;
        *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
fi

echo "Downloading uv..."
curl -fsSL "https://github.com/astral-sh/uv/releases/latest/download/uv-${TARGET}.tar.gz" \
    | tar xz -C "$WORK" --strip-components=1 "uv-${TARGET}/uv"
chmod +x "$UV"

# --- Clone the repo ----------------------------------------------------------
echo "Downloading Clarity (branch: $BRANCH)..."
git clone --depth 1 --branch "$BRANCH" "$REPO" "$WORK/clarity-agent"

# --- Hand off to Python ------------------------------------------------------
# Python detects the platform and handles everything from here.
"$UV" run --directory "$WORK/clarity-agent" python clarity.py install "${FORWARD_ARGS[@]+"${FORWARD_ARGS[@]}"}"
