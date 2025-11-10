#!/bin/bash
# Inkly CLI Installer for HPC(user-space, no sudo)
# Installs Node via nvm if missing (using curl or wget)
# Configures npm to a home-local prefix (~/.npm-global)
# Installs GitHub Copilot CLI globally (to ~/.npm-global/bin)
# Creates an 'inkly' alias (symlink) to the 'copilot' binary
# Sources Ink wrapper function (ink.sh) for the current user
# Verifies setup at the end


set -euo pipefail

echo "Installing Ink CLI (powered by GitHub Copilot)..."
# If 'node' isn't present, bootstrap nvm and install the latest LTS node.
echo "[1/6] Ensure Node (nvm) is available (user-space)…"
if ! command -v node >/dev/null 2>&1; then
  # Install nvm only if it's not already in ~/.nvm
  if [ ! -d "$HOME/.nvm" ]; then
    # Prefer curl; fall back to wget; fail with a clear message if neither exists.
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    else
      echo "Error: neither curl nor wget is available — please install one first." >&2
      exit 1
    fi
  fi
  # Load nvm into this shell, then install & use the latest LTS Node.js.
  # shellcheck disable=SC1090
  . "$HOME/.nvm/nvm.sh"
  nvm install --lts
  nvm use --lts
else
  echo "Node present: $(node -v)"
fi

echo "[2/6] Configure npm to install to ~/.npm-global (no sudo)…"
# Force npm global installs to land in ~/.npm-global (writeable by the user).
mkdir -p "$HOME/.npm-global"
npm config set prefix "$HOME/.npm-global"

# Ensure ~/.npm-global/bin is on PATH for future shells (idempotent).
if ! grep -q 'export PATH="$HOME/.npm-global/bin:$PATH"' "$HOME/.bashrc"; then
  echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"
fi

# Make the PATH change live in the current shell right now.
export PATH="$HOME/.npm-global/bin:$PATH"

echo "[3/6] Install GitHub Copilot CLI (npm)…"
# Install the official Copilot CLI (current supported distribution).
npm install -g @github/copilot

echo "[4/6] Expose 'inkly' alias next to 'copilot'…"
# Create a stable alias so wrapper can call 'inkly -p "...".
COPILOT_BIN="$(command -v copilot)"
mkdir -p "$HOME/.npm-global/bin"
ln -sf "$COPILOT_BIN" "$HOME/.npm-global/bin/inkly"

echo "[5/6] Add PATH for safety (idempotent)…"
# Ensure PATH includes the npm-global bin in this shell (even if .bashrc missed).
if ! echo "$PATH" | grep -q "$HOME/.npm-global/bin"; then
  export PATH="$HOME/.npm-global/bin:$PATH"
fi

echo "[6/6] Source the Ink wrapper function from the nested folder…"
# Auto-load ink() function on future shells; append only once.
if ! grep -q 'source ~/hpc-ink-setup/hpc-ink-setup/ink.sh' "$HOME/.bashrc"; then
  echo 'source ~/hpc-ink-setup/hpc-ink-setup/ink.sh' >> "$HOME/.bashrc"
fi
# Load it now for immediate use.
# shellcheck disable=SC1090
. "$HOME/.bashrc"

echo
echo "=== Verification ==="
# Print versions; never break the script if any of these are missing.
echo "node:      $(node -v)"
echo "npm:       $(npm -v)"
echo "copilot:   $(copilot --version || true)"
echo "inkly:     $(inkly --version || true)"
type ink || true
echo "Done."