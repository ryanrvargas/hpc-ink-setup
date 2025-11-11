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
echo "[1/6] Ensuring Node (nvm) is available (user-space)…"

if ! command -v node >/dev/null 2>&1; then
  # Install nvm only if missing
  if [ ! -d "$HOME/.nvm" ]; then
    echo "→ Installing nvm..."
    # Prefer curl; fall back to wget; fail clearly if neither exists
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    else
      echo "Error: neither curl nor wget is available — please install one first." >&2
      exit 1
    fi
  fi

  # Load nvm safely. Avoid nounset pitfalls by not using `set -u` yet.
  export NVM_DIR="$HOME/.nvm"
  if [ -s "$NVM_DIR/nvm.sh" ]; then
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh"
    nvm install --lts
    nvm use --lts
  else
    echo "Error: nvm.sh not found after installation." >&2
    exit 1
  fi
else
  echo "Node detected: $(node -v)"
fi


echo "[2/6] Configuring npm for user-space global installs…"
# Put global npm packages in ~/.npm-global (writeable by the user)
mkdir -p "$HOME/.npm-global"
npm config set prefix "$HOME/.npm-global"

# Persist PATH for future sessions (idempotent append)
if ! grep -q 'export PATH="$HOME/.npm-global/bin:$PATH"' "$HOME/.bashrc"; then
  echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"
fi
# Make PATH live in current shell immediately
export PATH="$HOME/.npm-global/bin:$PATH"

echo "[3/6] Installing GitHub Copilot CLI via npm…"
npm install -g @github/copilot

echo "[4/6] Creating 'inkly' alias…"

COPILOT_BIN="$(command -v copilot || true)"
if [ -z "$COPILOT_BIN" ]; then
  echo "Error: Copilot CLI not found after npm install." >&2
  exit 1
fi

# Ensure the bin dir exists and create/refresh the symlink
mkdir -p "$HOME/.npm-global/bin"
ln -sf "$COPILOT_BIN" "$HOME/.npm-global/bin/inkly"

echo "[5/6] Verifying PATH configuration…"
if ! echo "$PATH" | grep -q "$HOME/.npm-global/bin"; then
  export PATH="$HOME/.npm-global/bin:$PATH"
fi

echo "[6/6] Linking Ink wrapper (ink.sh)…"
# Auto-load your ink() function on future shells; append only once
if ! grep -q 'source ~/hpc-ink-setup/hpc-ink-setup/ink.sh' "$HOME/.bashrc"; then
  echo 'source ~/hpc-ink-setup/hpc-ink-setup/ink.sh' >> "$HOME/.bashrc"
fi

# Load it now for immediate use
# shellcheck disable=SC1090
. "$HOME/.bashrc"

echo
echo "=== Verification ==="
echo "node:      $(node -v)"
echo "npm:       $(npm -v)"
echo "copilot:   $(copilot --version || true)"
echo "inkly:     $(inkly --version || true)"
type ink || true   # Expected: "ink is a function"
echo
echo "Installation complete — open a new shell or run 'source ~/.bashrc' to activate Ink."