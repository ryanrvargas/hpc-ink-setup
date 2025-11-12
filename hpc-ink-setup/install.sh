#!/bin/bash
# Inkly CLI Installer for HPC (user-space, no sudo)
# Installs Node via nvm if missing (using curl or wget)
# Configures npm for a home-local prefix (~/.npm-global) without nvm conflicts
# Installs GitHub Copilot CLI globally (to ~/.npm-global/bin)
# Creates an 'inkly' alias (symlink) to the 'copilot' binary
# Sources Ink wrapper function (ink.sh) for the current user
# Verifies setup at the end

# --- CRLF self-fix ---
if file "$0" | grep -q "CRLF"; then
  echo "Converting Windows line endings to Unix (LF)..."
  sed -i 's/\r$//' "$0"
  exec bash "$0" "$@"
fi

set -eo pipefail

echo "Installing Ink CLI (powered by GitHub Copilot)..."

# [1/6] Ensure Node (nvm)
echo "[1/6] Ensuring Node (nvm) is available (user-space)…"
if ! command -v node >/dev/null 2>&1; then
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

  (
    set +u
    export NVM_DIR="$HOME/.nvm"
    . "$NVM_DIR/nvm.sh"
    nvm install --lts
    nvm use --lts
  )
  export NVM_DIR="$HOME/.nvm"
  . "$NVM_DIR/nvm.sh"
else
  echo "Node detected: $(node -v)"
fi

# [2/6] Configure npm (no nvm conflict)
echo "[2/6] Configuring npm for user-space installs…"

mkdir -p "$HOME/.npm-global"

# Clean up any conflicting prefix/globalconfig in .npmrc
if [ -f "$HOME/.npmrc" ]; then
  grep -Ev '^(globalconfig|prefix)' "$HOME/.npmrc" > "$HOME/.npmrc.tmp" || true
  mv "$HOME/.npmrc.tmp" "$HOME/.npmrc"
fi

# Use environment variable for prefix to avoid nvm warning
export NPM_CONFIG_PREFIX="$HOME/.npm-global"

# Ensure ~/.npm-global/bin is in PATH
if ! echo "$PATH" | grep -q "$HOME/.npm-global/bin"; then
  export PATH="$HOME/.npm-global/bin:$PATH"
  echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"
fi

# [3/6] Install GitHub Copilot CLI
echo "[3/6] Installing GitHub Copilot CLI via npm…"
npm install -g @github/copilot

# Immediately unset NPM_CONFIG_PREFIX so nvm stays active
unset NPM_CONFIG_PREFIX

# [4/6] Create 'inkly' alias for Copilot
echo "[4/6] Creating 'inkly' alias…"

COPILOT_BIN="$(command -v copilot || true)"
if [ -z "$COPILOT_BIN" ]; then
  echo "Error: Copilot CLI not found after npm install." >&2
  exit 1
fi

mkdir -p "$HOME/.npm-global/bin"

# Get absolute path to Node from nvm
NODE_PATH="$(nvm which current 2>/dev/null || command -v node)"
if [ -z "$NODE_PATH" ]; then
  echo "Error: Node binary not found — ensure nvm installed correctly." >&2
  exit 1
fi

# Create a launcher that explicitly calls Node with the Copilot CLI
cat <<EOF > "$HOME/.npm-global/bin/inkly"
#!/bin/bash
NODE_BIN="$NODE_PATH"
COPILOT_BIN="$COPILOT_BIN"

if [ ! -x "\$NODE_BIN" ]; then
  echo "Error: Node not found at \$NODE_BIN"
  exit 1
fi

exec "\$NODE_BIN" "\$COPILOT_BIN" "\$@"
EOF

chmod +x "$HOME/.npm-global/bin/inkly"


# [5/6] Verify PATH includes npm-global
echo "[5/6] Verifying PATH configuration…"
if ! echo "$PATH" | grep -q "$HOME/.npm-global/bin"; then
  export PATH="$HOME/.npm-global/bin:$PATH"
fi

# [6/6] Link Ink wrapper (ink.sh)
echo "[6/6] Linking Ink wrapper (ink.sh)…"
if ! grep -q "source ~/hpc-ink-setup/hpc-ink-setup/ink.sh" "$HOME/.bashrc"; then
  echo "source ~/hpc-ink-setup/hpc-ink-setup/ink.sh" >> "$HOME/.bashrc"
fi

# Activate in current shell
export PATH="$HOME/.npm-global/bin:$PATH"
source ~/hpc-ink-setup/hpc-ink-setup/ink.sh 2>/dev/null || true
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
NODE_PATH="$(nvm which current | xargs dirname)"
if ! echo "$PATH" | grep -q "$NODE_PATH"; then
  export PATH="$NODE_PATH:$PATH"
  echo "export PATH=\"$NODE_PATH:\$PATH\"" >> "$HOME/.bashrc"
fi
nvm use --delete-prefix v$(node -v | tr -d 'v') --silent

# --- Verification ---
echo
echo "=== Verification ==="
echo "node:      $(node -v)"
echo "npm:       $(npm -v)"
echo "copilot:   $(copilot --version || true)"
echo "inkly:     $(inkly --version || true)"
echo
echo "Installation complete — open a new shell or run 'source ~/.bashrc' to activate Ink."
echo
echo "Try:"
echo "  inkly -p \"Say hello\""
echo "  ink  \"Say hello\""
echo
echo "Activating Ink function for this shell..."
source ~/.bashrc
echo "Type 'inkly' and log in with GitHub."
