#!/bin/bash
# Inkly CLI Installer for HPC (user-space, no sudo)
# Installs Node via nvm if missing (using curl or wget)
# Configures npm for local (user-space) installs
# Installs the GitHub Copilot CLI binary instead of the npm package
# Creates a secure 'inkly' wrapper to block destructive commands
# Adds Copilot deny-list for safety
# Links the ink.sh helper
# Verifies setup at the end

set -eo pipefail  # Stop if any command fails

echo "Installing Ink CLI (powered by GitHub Copilot)..."

# [1/6] Node setup using nvm
echo "[1/6] Checking for Node (nvm)…"
if ! command -v node >/dev/null 2>&1; then
  if [ ! -d "$HOME/.nvm" ]; then
    echo "→ Installing nvm..."
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    else
      echo "Error: Need curl or wget installed." >&2
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

# [2/6] Configure npm for user-space installs
echo "[2/6] Configuring npm for user-space installs…"
mkdir -p "$HOME/.npm-global"
export NPM_CONFIG_PREFIX="$HOME/.npm-global"

# Clean out any old conflicting npmrc entries
if grep -Eq '^(globalconfig|prefix)' "$HOME/.npmrc" 2>/dev/null; then
  echo "→ Cleaning up old npm settings from ~/.npmrc"
  grep -Ev '^(globalconfig|prefix)' "$HOME/.npmrc" > "$HOME/.npmrc.tmp" && mv "$HOME/.npmrc.tmp" "$HOME/.npmrc"
fi

# Add to PATH if not already present
if ! grep -q 'export PATH="$HOME/.npm-global/bin:$PATH"' "$HOME/.bashrc"; then
  echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"
fi
export PATH="$HOME/.npm-global/bin:$PATH"

# [3/6] Install GitHub Copilot CLI (binary version)
echo "[3/6] Installing GitHub Copilot CLI binary…"
mkdir -p "$HOME/.npm-global/bin"

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)  ASSET="github-copilot-cli-linux-x64" ;;
  aarch64) ASSET="github-copilot-cli-linux-arm64" ;;
  *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

# Try to get latest release download URL
echo "→ Fetching latest release info from GitHub…"
if command -v curl >/dev/null 2>&1; then
  JSON=$(curl -fsSL https://api.github.com/repos/github/copilot-cli/releases/latest || true)
elif command -v wget >/dev/null 2>&1; then
  JSON=$(wget -qO- https://api.github.com/repos/github/copilot-cli/releases/latest || true)
else
  echo "Error: curl or wget required to download Copilot CLI." >&2
  exit 1
fi

# Extract download URL
DOWNLOAD_URL=$(printf '%s\n' "$JSON" | grep "browser_download_url" | grep "$ASSET" | cut -d '"' -f 4 | head -n1 || true)

# Fallback if GitHub API fails or rate-limited
if [ -z "$DOWNLOAD_URL" ]; then
  echo "⚠️  GitHub API may be rate-limited or missing asset. Using fallback URL..."
  DOWNLOAD_URL="https://github.com/github/copilot-cli/releases/latest/download/$ASSET"
fi

echo "→ Downloading from: $DOWNLOAD_URL"
if command -v curl >/dev/null 2>&1; then
  curl -L --progress-bar "$DOWNLOAD_URL" -o "$HOME/.npm-global/bin/copilot"
else
  wget --progress=bar:force "$DOWNLOAD_URL" -O "$HOME/.npm-global/bin/copilot"
fi

if [ ! -s "$HOME/.npm-global/bin/copilot" ]; then
  echo "❌ Download failed — file is empty or missing."
  exit 1
fi

chmod +x "$HOME/.npm-global/bin/copilot"
echo "✓ Copilot CLI installed successfully."


# [4/6] Create secure Inkly wrapper
echo "[4/6] Creating secure 'inkly' wrapper..."
mkdir -p "$HOME/.npm-global/bin"

cat <<'EOF' > "$HOME/.npm-global/bin/inkly"
#!/bin/bash
# Inkly Secure Wrapper — prevents file modification and lets you run 'inkly "prompt"'

set -euo pipefail

# Make sure copilot binary exists
COPILOT_BIN="$(command -v copilot || echo "$HOME/.npm-global/bin/copilot")"
if [ ! -x "$COPILOT_BIN" ]; then
  echo "Error: GitHub Copilot CLI not found or not executable."
  exit 1
fi

# Restricted shell commands (deny-list)
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

# No args → interactive mode
if [ "$#" -eq 0 ]; then
  exec "$COPILOT_BIN" "${deny_flags[@]}"
fi

# Combine user input into one prompt string
prompt_text="$*"

# Filter dangerous commands in the prompt
if printf '%s' "$prompt_text" | grep -Eiq '\b(rm|mv|unlink|dd|chmod|chown|rmdir|sudo)\b|cp[[:space:]]+-r'; then
  echo "❌ Operation blocked: destructive command detected."
  echo "Inkly runs in safe mode — no file deletions or system changes allowed."
  exit 1
fi

# Try the normal -p mode first; fallback to suggest if CLI format changed
"$COPILOT_BIN" -p "$prompt_text" "${deny_flags[@]}" 2> >(tee /tmp/inkly_error.log >&2)
status=$?
if grep -q "Invalid command format" /tmp/inkly_error.log; then
  exec "$COPILOT_BIN" suggest "$prompt_text" "${deny_flags[@]}"
else
  exit $status
fi
EOF

chmod +x "$HOME/.npm-global/bin/inkly"

# [5/6] Add Copilot deny-list config
echo "[5/6] Creating Copilot deny-list config..."
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

# [6/6] Link Ink wrapper (ink.sh)
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
echo "Installation complete — Inkly is ready."
echo "Try:"
echo "  inkly -p \"Say hello\""
echo "  inkly \"Say hello\""
set -e

# Reload the shell so it works immediately
hash -r
echo
echo "Reloading shell so Inkly and Copilot work now..."
SHELL_PATH="${SHELL:-/bin/bash}"
exec "$SHELL_PATH" -l
