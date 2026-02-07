#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Zap Empire: Mint Setup ==="

# Source mint environment
set -a
source "$PROJECT_DIR/mint.env"
set +a

# Create data directory for mint
mkdir -p "$PROJECT_DIR/data/mint"

echo "Starting Cashu mint on http://127.0.0.1:${MINT_LISTEN_PORT}..."
exec python -m cashu.mint.app
