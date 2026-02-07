#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STRFRY_BIN="$PROJECT_DIR/strfry"

echo "=== Zap Empire: Relay Setup ==="

# Check if strfry binary exists
if [ ! -f "$STRFRY_BIN" ]; then
    echo "strfry not found. Building from source..."

    # Install dependencies
    sudo apt-get update
    sudo apt-get install -y git build-essential libyaml-cpp-dev zlib1g-dev \
        libssl-dev liblmdb-dev libflatbuffers-dev libsecp256k1-dev pkg-config

    # Clone and build
    TEMP_DIR=$(mktemp -d)
    git clone https://github.com/hoytech/strfry.git "$TEMP_DIR/strfry"
    cd "$TEMP_DIR/strfry"
    git submodule update --init
    make setup-golpe
    make -j$(nproc)

    # Copy binary to project
    cp strfry "$STRFRY_BIN"
    cd "$PROJECT_DIR"
    rm -rf "$TEMP_DIR"

    echo "strfry built successfully."
else
    echo "strfry binary found."
fi

# Create database directory
mkdir -p "$PROJECT_DIR/strfry-db"

echo "Starting strfry relay on ws://127.0.0.1:7777..."
exec "$STRFRY_BIN" --config="$PROJECT_DIR/strfry.conf" relay
