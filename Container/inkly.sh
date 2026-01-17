#!/bin/bash
#
# Inkly unified build and install script
#
# This script combines the behavior of:
# - build.sh   (container build)
# - install.sh (ink launcher install)
# - run.sh     (orchestration and smoke test)
#
# No additional logic has been added.

set -euo pipefail

echo "Running Inkly build and install"

# ------------------------------------------------------------
# Build step (from build.sh)
# ------------------------------------------------------------
echo "==> Creating Inkly directory"
mkdir -p "$HOME/.inkly"

echo "==> Building Inkly container"
apptainer build "$HOME/.inkly/inkly1.sif" inkly1.def

echo "==> Build complete"
echo "Container installed at ~/.inkly/inkly1.sif"

# ------------------------------------------------------------
# Install step (from install.sh)
# ------------------------------------------------------------
echo "==> Installing ink launcher"

mkdir -p "$HOME/.local/bin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cp -f "$SCRIPT_DIR/ink" "$HOME/.local/bin/ink"
chmod +x "$HOME/.local/bin/ink"

echo "==> ink installed to ~/.local/bin/ink"
echo
echo "Make sure ~/.local/bin is in your PATH:"
echo "export PATH=\"\$HOME/.local/bin:\$PATH\""

# ------------------------------------------------------------
# Run step (from run.sh)
# ------------------------------------------------------------
echo "Inkly build and install complete"

ink "Hello"
