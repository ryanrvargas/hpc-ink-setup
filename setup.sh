#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

INKLY_HOME="$HOME/.inkly"
VENV_DIR="$INKLY_HOME/venv"
VENV_PYTHON="$VENV_DIR/bin/python"

SCRAPER_REPO="${SCRAPER_REPO:-https://github.com/thealice-lab/gaussian-docs-scraper.git}"
SCRAPER_REF="${SCRAPER_REF:-integration/inkly-phase1}"
SCRAPER_DIR="${SCRAPER_DIR:-$INKLY_HOME/src/gaussian-docs-scraper}"

echo "Inkly setup"
echo "Repository: $REPO_ROOT"
echo "Inkly home: $INKLY_HOME"

"$PYTHON" --version

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Creating Inkly Python environment at $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
else
    echo "Using existing Inkly Python environment at $VENV_DIR"
fi

echo "Installing Inkly Python requirements"
"$VENV_PYTHON" -m pip install -r "$REPO_ROOT/requirements.txt"

if [[ ! -d "$SCRAPER_DIR/.git" ]]; then
    echo "Cloning Gaussian docs scraper"
    mkdir -p "$(dirname "$SCRAPER_DIR")"
    git clone --branch "$SCRAPER_REF" "$SCRAPER_REPO" "$SCRAPER_DIR"
else
    echo "Using existing Gaussian docs scraper at $SCRAPER_DIR"
fi

echo "Installing Gaussian docs scraper"
"$VENV_PYTHON" -m pip install -e "$SCRAPER_DIR"

echo "Installing Inkly"
"$VENV_PYTHON" "$REPO_ROOT/install.py"

echo "Verifying Gaussian documentation search import"
"$VENV_PYTHON" -c \
    "from gaussian_scraper.search import search_docs; print('Gaussian scraper import: OK')"

echo
echo "Inkly setup complete."
echo "Launcher: $INKLY_HOME/bin/ink"
