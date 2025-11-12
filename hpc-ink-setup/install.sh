#!/bin/bash
# Inkly CLI Installer for HPC (user-space, no sudo)
# Installs Node via nvm if missing (using curl or wget)
# Configures npm to a home-local prefix (~/.npm-global)
# Installs GitHub Copilot CLI globally (to ~/.npm-global/bin)
# Creates a secure 'inkly' wrapper to block destructive commands
# Adds Copilot global deny-list for dangerous tools
# Sources Ink wrapper (ink.sh)
# Verifies setup

set -eo pipefail # Exit the script if any command fails

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
      echo "Error: neither curl nor wget is available." >&2
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

# [2/6] Configure npm user-space installs
echo "[2/6] Configuring npm for user-space global installs…"
mkdir -p "$HOME/.npm-global"
# Avoid modifying ~/.npmrc directly — just export PREFIX for this session
export NPM_CONFIG_PREFIX="$HOME/.npm-global"

if grep -Eq '^(globalconfig|prefix)' "$HOME/.npmrc" 2>/dev/null; then
  echo "→ Cleaning up incompatible npm settings from ~/.npmrc"
  grep -Ev '^(globalconfig|prefix)' "$HOME/.npmrc" > "$HOME/.npmrc.tmp" && mv "$HOME/.npmrc.tmp" "$HOME/.npmrc"
fi

if ! grep -q 'export PATH="$HOME/.npm-global/bin:$PATH"' "$HOME/.bashrc"; then
  echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"
fi
export PATH="$HOME/.npm-global/bin:$PATH"

# [3/6] Install GitHub Copilot CLI
echo "[3/6] Installing GitHub Copilot CLI via npm…"
npm install -g @github/copilot

# [4/6] Create secure 'inkly' wrapper
echo "[4/6] Creating secure 'inkly' wrapper…"
mkdir -p "$HOME/.npm-global/bin"

cat <<'EOF' > "$HOME/.npm-global/bin/inkly"
#!/bin/bash
# Inkly Secure Wrapper — blocks destructive commands and allows 'inkly "command"' usage safely

set -euo pipefail

# Auto-detect Copilot CLI binary (handles all known npm layouts)
COPILOT_ROOT="$(npm root -g)/@github/copilot"

if [ -f "$COPILOT_ROOT/bin/copilot.js" ]; then
  COPILOT_BIN="$COPILOT_ROOT/bin/copilot.js"
elif [ -f "$COPILOT_ROOT/cli.js" ]; then
  COPILOT_BIN="$COPILOT_ROOT/cli.js"
elif [ -f "$COPILOT_ROOT/node_modules/@github/copilot-cli/bin/copilot.js" ]; then
  COPILOT_BIN="$COPILOT_ROOT/node_modules/@github/copilot-cli/bin/copilot.js"
elif [ -f "$(npm root -g)/@github/copilot-cli/bin/copilot.js" ]; then
  COPILOT_BIN="$(npm root -g)/@github/copilot-cli/bin/copilot.js"
else
  echo "Error: Could not locate GitHub Copilot CLI binary."
  echo "Checked:"
  echo "  $COPILOT_ROOT/bin/copilot.js"
  echo "  $COPILOT_ROOT/cli.js"
  echo "  $COPILOT_ROOT/node_modules/@github/copilot-cli/bin/copilot.js"
  echo "  $(npm root -g)/@github/copilot-cli/bin/copilot.js"
  exit 1
fi



deny_flags=(
  --deny-tool 'shell(rm:*)'
  --deny-tool 'shell(sudo:*)'
  --deny-tool 'shell(chmod:*)'
  --deny-tool 'shell(chown:*)'
  --deny-tool 'shell(rmdir:*)'
  --deny-tool 'shell(unlink:*)'
  --deny-tool 'shell(cp:*)'
  --deny-tool 'shell(mv:*)'
)

# No arguments → interactive Copilot mode
if [ "$#" -eq 0 ]; then
  exec node "$COPILOT_BIN" "${deny_flags[@]}"
fi

prompt_text="$*"

# Block risky strings
if printf '%s' "$prompt_text" | grep -Eiq '\b(rm|mv|unlink|dd|chmod|chown|rmdir|sudo)\b|cp[[:space:]]+-r[[:space:]]+/' ; then
  echo "❌ Operation blocked: destructive command detected in prompt."
  echo "Inkly runs in safe mode — deleting or modifying files is not allowed."
  exit 1
fi

# Try -p syntax first, then fallback to suggest if needed
node "$COPILOT_BIN" -p "$prompt_text" "${deny_flags[@]}" 2> >(tee /tmp/inkly_error.log >&2)
status=$?
if grep -q "Invalid command format" /tmp/inkly_error.log; then
  exec node "$COPILOT_BIN" suggest "$prompt_text" "${deny_flags[@]}"
else
  exit $status
fi
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
set +e
echo
echo "=== Verification ==="
echo "node:      $(node -v 2>/dev/null)"
echo "npm:       $(npm -v 2>/dev/null)"
echo "copilot:   $(copilot --version 2>/dev/null || true)"
echo "inkly:     $(inkly --version 2>/dev/null || true)"
echo
echo "Installation complete — you can start using Ink right away."
echo "Try:"
echo "  inkly -p \"Say hello\""
echo "  inkly \"Say hello\""
set -e

# --- Reload shell so inkly/copilot work immediately in this terminal ---
hash -r
echo
echo "Reloading your shell to pick up PATH/NVM changes..."
SHELL_PATH="${SHELL:-/bin/bash}"
exec "$SHELL_PATH" -l
