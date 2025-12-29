#!/bin/bash
set -euo pipefail

echo "Installing ink launcher"

mkdir -p "$HOME/.local/bin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

ln -sf "$SCRIPT_DIR/ink" "$HOME/.local/bin/ink"

echo "ink installed to $HOME/.local/bin/ink"
echo "Ensure ~/.local/bin is in your PATH"
