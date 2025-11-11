#!/bin/bash
# Inkly CLI Installer for HPC(user-space, no sudo)
# Installs Node via nvm if missing (using curl or wget)
# Configures npm to a home-local prefix (~/.npm-global)
# Installs GitHub Copilot CLI globally (to ~/.npm-global/bin)
# Creates an 'inkly' alias (symlink) to the 'copilot' binary
# Sources Ink wrapper function (ink.sh) for the current user
# Verifies setup at the end


set -eo pipefail

echo "Installing Ink CLI (powered by GitHub Copilot)..."

# 1. Ensure Node (nvm) is available
echo "[1/6] Ensuring Node (nvm) is available (user-space)…"

if ! command -v node >/dev/null 2>&1; then
  # Install nvm if it doesn't exist
  if [ ! -d "$HOME/.nvm" ]; then
    echo "→ Installing nvm..."
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    else
      echo "Error: neither curl nor wget is available — please install one first." >&2
      exit 1
    fi
  fi

  # Run nvm in a subshell to avoid 'set -u' issues
  (
    set +u
    export NVM_DIR="$HOME/.nvm"
    . "$NVM_DIR/nvm.sh"
    nvm install --lts
    nvm use --lts
  )
  # Re-load nvm into the parent shell so npm is accessible
    export NVM_DIR="$HOME/.nvm"
    . "$NVM_DIR/nvm.sh"
else
  echo "Node detected: $(node -v)"
fi

# 2. Configure npm for user-space installs
echo "[2/6] Configuring npm for user-space global installs…"

mkdir -p "$HOME/.npm-global"
npm config set prefix "$HOME/.npm-global"

# Add ~/.npm-global/bin to PATH if not already present
if ! grep -q 'export PATH="$HOME/.npm-global/bin:$PATH"' "$HOME/.bashrc"; then
  echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"
fi

export PATH="$HOME/.npm-global/bin:$PATH"

# 3. Install GitHub Copilot CLI
echo "[3/6] Installing GitHub Copilot CLI via npm…"
npm install -g @github/copilot

# 4. Create 'inkly' alias for Copilot
echo "[4/6] Creating 'inkly' alias…"

COPILOT_BIN="$(command -v copilot || true)"
if [ -z "$COPILOT_BIN" ]; then
  echo "Error: Copilot CLI not found after npm install." >&2
  exit 1
fi

mkdir -p "$HOME/.npm-global/bin"
ln -sf "$COPILOT_BIN" "$HOME/.npm-global/bin/inkly"

# 5. Verify PATH includes npm-global
echo "[5/6] Verifying PATH configuration…"

if ! echo "$PATH" | grep -q "$HOME/.npm-global/bin"; then
  export PATH="$HOME/.npm-global/bin:$PATH"
fi

# 6. Source Ink wrapper function
echo "[6/6] Linking Ink wrapper (ink.sh)…"

if ! grep -q 'source ~/hpc-ink-setup/hpc-ink-setup/ink.sh' "$HOME/.bashrc"; then
  echo 'source ~/hpc-ink-setup/hpc-ink-setup/ink.sh' >> "$HOME/.bashrc"
fi

. "$HOME/.bashrc"

# Make inkly and ink available immediately in this shell
export PATH="$HOME/.npm-global/bin:$PATH"
source ~/hpc-ink-setup/hpc-ink-setup/ink.sh
export -f ink


echo
echo "=== Verification ==="
echo "node:      $(node -v)"
echo "npm:       $(npm -v)"
echo "copilot:   $(copilot --version || true)"
echo "inkly:     $(inkly --version || true)"
type ink || true
echo
echo "Installation complete — open a new shell or run 'source ~/.bashrc' to activate Ink."
echo
echo "Try:"
echo "  inkly -p \"Say hello\""
echo "  ink  \"Say hello\""

echo "Activating Ink for this shell..."
exec bash --rcfile ~/.bashrc
echo "Starting Inkly(Powered by Copilot)"
exec bash inkly