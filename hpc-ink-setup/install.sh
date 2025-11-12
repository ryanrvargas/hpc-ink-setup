#!/bin/bash
# Inkly CLI Installer for HPC (user-space, no sudo)
# Installs Node via nvm if missing (using curl or wget)
# Configures npm to a home-local prefix (~/.npm-global)
# Installs GitHub Copilot CLI globally (to ~/.npm-global/bin)
# Creates a secure 'inkly' wrapper to block destructive commands
# Adds a Copilot global deny-list for dangerous tools
# Sources Ink wrapper (ink.sh)
# Verifies setup

set -eo pipefail # Exit the script if any command fails

echo "Installing Ink CLI (powered by GitHub Copilot)..."

# [1/6] Ensure Node (nvm)
echo "[1/6] Ensuring Node (nvm) is available (user-space)…"
if ! command -v node >/dev/null 2>&1; then # Checks if node is installed; if not, install in the home directory
  if [ ! -d "$HOME/.nvm" ]; then # Downloads and runs the nvm install script through curl or wget
    echo "→ Installing nvm..."
    if command -v curl >/dev/null 2>&1; then # If curl is installed, use it
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    elif command -v wget >/dev/null 2>&1; then # If wget is installed, use it
      wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    else
      echo "Error: neither curl nor wget is available." >&2
      exit 1
    fi
  fi
  ( # Install the latest Node version. Subshell keeps it isolated so the environment loads correctly
    set +u  # Turn off unset variable errors temporarily
    export NVM_DIR="$HOME/.nvm" # Tell nvm where to live and look at $NVM_DIR; using $HOME makes it per-user
    . "$NVM_DIR/nvm.sh" # . = source in bash; source nvm loader into this subshell
    nvm install --lts
    nvm use --lts
  )
  export NVM_DIR="$HOME/.nvm" # Then load into the current shell so npm and node work immediately
  . "$NVM_DIR/nvm.sh"
else
  echo "Node detected: $(node -v)"
fi

# [2/6] Configure npm user-space installs
echo "[2/6] Configuring npm for user-space global installs…"
mkdir -p "$HOME/.npm-global" # Tell npm to install global packages in ~/.npm-global instead of a system directory to avoid permission errors
npm config set prefix "$HOME/.npm-global" # Tells npm to install into ~/.npm-global

# Remove hardcoded prefix settings that conflict with nvm's dynamic path
if grep -Eq '^(globalconfig|prefix)' "$HOME/.npmrc" 2>/dev/null; then # Check if ~/.npmrc contains a line that starts with globalconfig or prefix
  echo "→ Cleaning up incompatible npm settings from ~/.npmrc"
  grep -Ev '^(globalconfig|prefix)' "$HOME/.npmrc" > "$HOME/.npmrc.tmp" && mv "$HOME/.npmrc.tmp" "$HOME/.npmrc"
fi
# Ensure that executables installed through npm can be run from anywhere
if ! grep -q 'export PATH="$HOME/.npm-global/bin:$PATH"' "$HOME/.bashrc"; then # Check if .bashrc already contains that exact export line; if not, append
  echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc" # Append the export so future shells include ~/.npm-global/bin at the front of PATH
fi
export PATH="$HOME/.npm-global/bin:$PATH" # Update PATH for the current shell session

# [3/6] Install GitHub Copilot CLI
echo "[3/6] Installing GitHub Copilot CLI via npm…"
npm install -g @github/copilot # -g installs globally 

# [4/6] Create secure 'inkly' wrapper
echo "[4/6] Creating secure 'inkly' wrapper…" # COPILOT_BIN is our result: either a path or an empty string
COPILOT_BIN="$(command -v copilot || true)" # Find full path to the copilot executable. command -v copilot returns the path if found; $() captures the output into a variable
if [ -z "$COPILOT_BIN" ]; then # If the string length is 0, copilot is not found
  echo "Error: Copilot CLI not found after npm install." >&2
  exit 1
fi

mkdir -p "$HOME/.npm-global/bin"

# --- Secure Wrapper (prevents destructive commands and recursion) ---
mkdir -p "$HOME/.npm-global/bin"

cat <<'EOF' > "$HOME/.npm-global/bin/inkly"
#!/bin/bash
# Inkly Secure Wrapper — blocks destructive commands and allows 'inkly "command"' usage safely

set -euo pipefail

# Auto-detect Copilot CLI binary for both legacy and new npm layouts
COPILOT_ROOT="$(npm root -g)/@github/copilot"
if [ -f "$COPILOT_ROOT/bin/copilot.js" ]; then
  COPILOT_BIN="$COPILOT_ROOT/bin/copilot.js"
elif [ -f "$COPILOT_ROOT/node_modules/@github/copilot-cli/bin/copilot.js" ]; then
  COPILOT_BIN="$COPILOT_ROOT/node_modules/@github/copilot-cli/bin/copilot.js"
else
  echo "Error: Could not locate GitHub Copilot CLI entrypoint under $COPILOT_ROOT"
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

# Try legacy (-p) and new (suggest) Copilot modes automatically
node "$COPILOT_BIN" -p "$prompt_text" "${deny_flags[@]}" 2> >(tee /tmp/inkly_error.log >&2)
status=$?
if grep -q "Invalid command format" /tmp/inkly_error.log; then
  exec node "$COPILOT_BIN" suggest "$prompt_text" "${deny_flags[@]}"
else
  exit $status
fi
EOF

chmod +x "$HOME/.npm-global/bin/inkly"

# [5/6] Add Copilot global deny-list (Option 3)
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

if ! grep -q "source $HOME/hpc-ink-setup/hpc-ink-setup/ink.sh" "$HOME/.bashrc"; then # Search .bashrc for the exact line; ! flips the logic so if .bashrc doesn’t already contain this line, add it
  echo "source $HOME/hpc-ink-setup/hpc-ink-setup/ink.sh" >> "$HOME/.bashrc" # Append to .bashrc
fi

{ # Activate everything
  export PATH="$HOME/.npm-global/bin:$PATH" # Add npm-global to PATH so inkly and copilot are runnable immediately 
  source "$HOME/hpc-ink-setup/hpc-ink-setup/ink.sh" >/dev/null 2>&1 # Load ink.sh
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
echo "Type 'inkly' and log in with GitHub."
echo
echo "Try:"
echo "  inkly -p \"Say hello\""
echo "  ink  \"Say hello\""
