#!/bin/bash
set -e

echo "==> Creating Inkly directory"
mkdir -p "$HOME/.inkly"

echo "==> Building Inkly container"
apptainer build "$HOME/.inkly/inkly1.sif" inkly.def

echo "==> Build complete"
echo "Container installed at ~/.inkly/inkly1.sif"
