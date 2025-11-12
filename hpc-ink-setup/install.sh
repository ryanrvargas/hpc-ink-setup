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

# [4/6] Create secure 'inkly' wrapper
echo "[4/6] Creating secure 'inkly' wrapper…"
COPILOT_BIN="$(command -v copilot || true)"
if [ -z "$COPILOT_BIN" ]; then
  echo "Error: Copilot CLI not found after npm install." >&2
  exit 1
fi

mkdir -p "$HOME/.npm-global/bin"

cat <<'EOF' > "$HOME/.npm-global/bin/inkly"
#!/bin/bash
# Inkly Secure Wrapper — blocks destructive commands

COPILOT_BIN="$(command -v copilot)"
ARGS="$*"

# Block risky command strings
if echo "$ARGS" | grep -Eq '\b(rm|mv|unlink|dd|chmod|chown|rmdir|cp\s+-r\s+/|sudo)\b'; then
  echo "❌ Operation blocked: destructive command detected in prompt."
  echo "Inkly runs in safe mode — deleting or modifying files is not allowed."
  exit 1
fi

# Run Copilot with deny-tool guard
"$COPILOT_BIN" "$@" \
  --deny-tool 'shell(rm:*)' \
  --deny-tool 'shell(sudo:*)' \
  --deny-tool 'shell(chmod:*)' \
  --deny-tool 'shell(chown:*)' \
  --deny-tool 'shell(rmdir:*)' \
  --deny-tool 'shell(unlink:*)' \
  --deny-tool 'shell(cp:*)' \
  --deny-tool 'shell(mv:*)'
EOF

chmod +x "$HOME/.npm-global/bin/inkly"

# [5/6] Add Copilot global deny-list
echo "[5/6] Setting Copilot global deny-list…"
mkdir -p "$HOME/.copilot"
cat <<'EOF' > "$HOME/.copilot/config.json"
{
  "toolPermissions": {
    "deny": [
      "shell(rm:*)",
      "shell(sudo:*)",
      "shell(chmod:*)",
      "shell(chown:*)",
      "shell(rmdir:*)",
      "shell(unlink:*)",
      "shell(cp:*)",
      "shell(mv:*)"
    ]
  }
}
EOF

# [6/6] Link Ink wrapper
echo "[6/6] Linking Ink wrapper (ink.sh)…"
if ! grep -q "source $HOME/hpc-ink-setup/hpc-ink-setup/ink.sh" "$HOME/.bashrc"; then
  echo "source $HOME/hpc-ink-setup/hpc-ink-setup/ink.sh" >> "$HOME/.bashrc"
fi

{
  export PATH="$HOME/.npm-global/bin:$PATH"
  source "$HOME/hpc-ink-setup/hpc-ink-setup/ink.sh" >/dev/null 2>&1
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" >/dev/null 2>&1
  nvm use --delete-prefix v$(node -v | tr -d 'v') --silent
} 2>/dev/null

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
