#!/bin/bash
set -e

echo "==> Installing ink launcher"

mkdir -p "$HOME/.local/bin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cp "$SCRIPT_DIR/ink" "$HOME/.local/bin/ink"
chmod +x "$HOME/.local/bin/ink"

echo "==> ink installed to ~/.local/bin/ink"

echo ""
echo "Make sure ~/.local/bin is in your PATH:"
echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
