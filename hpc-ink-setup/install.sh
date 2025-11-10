#!/bin/bash
# Inkly CLI Installer for HPC
# Wraps GitHub Copilot CLI under the "ink" command
# Run this on your HPC cluster

set -euo pipefail

echo "Installing Ink CLI (powered by GitHub Copilot)..."
echo "[1/6] Ensure Node (nvm) is available (user-space)…"
if ! command -v node >/dev/null 2>&1; then
  if [ ! -d "$HOME/.nvm" ]; then
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    else
      echo "Error: neither curl nor wget is available — please install one first." >&2
      exit 1
    fi
  fi
  # shellcheck disable=SC1090
  . "$HOME/.nvm/nvm.sh"
  nvm install --lts
  nvm use --lts
else
  echo "Node present: $(node -v)"
fi

echo "[2/6] Configure npm to install to ~/.npm-global (no sudo)…"
mkdir -p "$HOME/.npm-global"
npm config set prefix "$HOME/.npm-global"
if ! grep -q 'export PATH="$HOME/.npm-global/bin:$PATH"' "$HOME/.bashrc"; then
  echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"
fi
# Make it live for this shell
export PATH="$HOME/.npm-global/bin:$PATH"

echo "[3/6] Install GitHub Copilot CLI (npm)…"
npm install -g @github/copilot

echo "[4/6] Expose 'inkly' alias next to 'copilot'…"
COPILOT_BIN="$(command -v copilot)"
mkdir -p "$HOME/.npm-global/bin"
ln -sf "$COPILOT_BIN" "$HOME/.npm-global/bin/inkly"

echo "[5/6] Add PATH for safety (idempotent)…"
if ! echo "$PATH" | grep -q "$HOME/.npm-global/bin"; then
  export PATH="$HOME/.npm-global/bin:$PATH"
fi

echo "[6/6] Source the Ink wrapper function from the nested folder…"
if ! grep -q 'source ~/hpc-ink-setup/hpc-ink-setup/ink.sh' "$HOME/.bashrc"; then
  echo 'source ~/hpc-ink-setup/hpc-ink-setup/ink.sh' >> "$HOME/.bashrc"
fi
# shellcheck disable=SC1090
. "$HOME/.bashrc"

echo
echo "=== Verification ==="
echo "node:      $(node -v)"
echo "npm:       $(npm -v)"
echo "copilot:   $(copilot --version || true)"
echo "inkly:     $(inkly --version || true)"
type ink || true
echo "Done."