#!/bin/bash
# Inkly CLI Installer for HPC (user-space, no sudo)
# Installs Node via nvm if missing (using curl or wget)
# Configures npm for a home-local prefix (~/.npm-global) without nvm conflicts
# Installs GitHub Copilot CLI globally (to ~/.npm-global/bin)
# Creates an 'inkly' alias/wrapper around the 'copilot' binary
# Installs 'ink' HPC-aware wrapper (ink.sh)
# Verifies setup at the end

# --- CRLF self-fix ---
if file "$0" | grep -q "CRLF"; then          # Detect Windows line endings so Bash won’t choke.
  echo "Converting Windows line endings to Unix (LF)..."
  sed -i 's/\r$//' "$0"                      # Strip carriage returns in place.
  exec bash "$0" "$@"                        # Re-exec the now-fixed script.
fi

set -eo pipefail                              # Exit on error and fail a pipeline if any command fails.

INKLY_HOME="$HOME/.inkly"
COPILOT_STATE="$INKLY_HOME/copilot"

mkdir -p "$COPILOT_STATE"

# Force Copilot to use a persistent, explicit config dir
export COPILOT_CONFIG_DIR="$COPILOT_STATE"

export PATH="$HOME/.npm-global/bin:$PATH"     # Ensure user-global npm bin is in PATH for the install session.

echo "Installing Ink CLI (powered by GitHub Copilot)..."

# [1/5] Ensure Node (nvm)
echo "[1/5] Ensuring Node (nvm) is available (user-space)…"
if ! command -v node >/dev/null 2>&1; then    # If Node isn’t available, install via nvm.
  if [ ! -d "$HOME/.nvm" ]; then              # Install nvm only if not already present.
    echo "→ Installing nvm..."
    if command -v curl >/dev/null 2>&1; then  # Prefer curl if available.
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    elif command -v wget >/dev/null 2>&1; then  # Fall back to wget if curl is missing.
      wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    else
      echo "Error: neither curl nor wget is available — please install one first." >&2
      exit 1
    fi
  fi

  (
    # Use a subshell so nvm env tweaks don’t leak if set -u later.
    set +u                                    # Loosen undefined-var checks for nvm’s scripts.
    export NVM_DIR="$HOME/.nvm"               # Tell nvm where it lives.
    . "$NVM_DIR/nvm.sh"                       # Load nvm into the shell.
    echo "Installing latest LTS Node via nvm..."
    nvm install --lts                         # Install latest LTS Node for stability.
    nvm use --lts                             # Activate that Node version for this shell.
  )
  export NVM_DIR="$HOME/.nvm"                 # Persist nvm path for parent shell.
  . "$NVM_DIR/nvm.sh"                         # Reload nvm so node/npm are available now.
else
  echo "Node detected: $(node -v)"
fi

# [2/5] Configure npm (no nvm conflict)
echo "[2/5] Configuring npm for user-space installs…"

mkdir -p "$HOME/.npm-global"                  # Create a user-writable global prefix for npm.

# Clean up any conflicting prefix/globalconfig in .npmrc
if [ -f "$HOME/.npmrc" ]; then
  grep -Ev '^(globalconfig|prefix)' "$HOME/.npmrc" > "$HOME/.npmrc.tmp" || true  # Remove settings that fight nvm.
  mv "$HOME/.npmrc.tmp" "$HOME/.npmrc"
fi

export NPM_CONFIG_PREFIX="$HOME/.npm-global"  # Use env var prefix to avoid nvm’s “prefix” warning.

# Ensure ~/.npm-global/bin is in PATH
if ! echo "$PATH" | grep -q "$HOME/.npm-global/bin"; then
  export PATH="$HOME/.npm-global/bin:$PATH"   # Make globally installed npm binaries runnable.
  echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"  # Persist in future shells.
fi

# [3/5] Install GitHub Copilot CLI
echo "[3/5] Installing GitHub Copilot CLI via npm…"
npm install -g @github/copilot                # Install Copilot CLI into the user prefix.

unset NPM_CONFIG_PREFIX                       # Unset prefix env so nvm remains fully happy afterward.

# [4/5] Create secure 'inkly' wrapper…
echo "[4/5] Creating secure 'inkly' wrapper…"

mkdir -p "$HOME/.npm-global/bin"              # Ensure the bin dir for our wrapper exists.

# Generate the inkly wrapper script that safely fronts Copilot.
cat <<'EOF' > "$HOME/.npm-global/bin/inkly"
#!/bin/bash
set -euo pipefail

# Force Inkly to use the npm-installed Copilot
COPILOT_BIN="$HOME/.npm-global/bin/copilot"

if [ ! -x "$COPILOT_BIN" ]; then
  echo "Error: GitHub Copilot CLI not found at $COPILOT_BIN" >&2
  exit 1
fi

deny_flags=(
  --disable-parallel-tools-execution
  --deny-tool 'shell(rm:*)'
  --deny-tool 'shell(sudo:*)'
  --deny-tool 'shell(chmod:*)'
  --deny-tool 'shell(chown:*)'
  --deny-tool 'shell(rmdir:*)'
  --deny-tool 'shell(unlink:*)'
  --deny-tool 'shell(cp:*)'
  --deny-tool 'shell(mv:*)'
)

clean_output() {
  sed -e '/^Total usage est:/,/^Usage by model:/d' \
      -e '/^Usage by model:/d' \
      -e '/^[[:space:]]*claude-.*Premium request)/d'
}

# No args → fully interactive Copilot (preserve TUI; do NOT pipe through clean_output)
if [ "$#" -eq 0 ]; then
  exec "$COPILOT_BIN" "${deny_flags[@]}"
fi

case "$1" in
  -*)
    exec "$COPILOT_BIN" "$@" "${deny_flags[@]}" ;;
  help|--help|-h|login|logout|whoami|version|update|suggest|chat|terms)
    exec "$COPILOT_BIN" "$@" "${deny_flags[@]}" ;;
esac

prompt="$*"

# Block dangerous commands
if printf '%s' "$prompt" | grep -Eiq '\b(rm|mv|unlink|dd|chmod|chown|rmdir|sudo)\b|cp[[:space:]]+-r'; then
  echo "Operation blocked: destructive command detected in prompt."
  exit 1
fi

# Prompt mode: run Copilot then strip usage footer / model stats
"$COPILOT_BIN" -p "$prompt" "${deny_flags[@]}" 2>&1 | clean_output
exit $?
EOF

chmod +x "$HOME/.npm-global/bin/inkly"        # Make the wrapper executable.

echo "[5/5] Installing ink launcher…"

INKLY_BIN="$INKLY_HOME/bin"
mkdir -p "$INKLY_BIN"

# Copy ink.sh into persistent Inkly bin
cp -f "$(cd "$(dirname "$0")" && pwd)/ink.sh" "$INKLY_BIN/ink.sh"
chmod +x "$INKLY_BIN/ink.sh"

# Install ink launcher
cat <<'LAUNCH' > "$HOME/.npm-global/bin/ink"
#!/bin/bash
exec "$HOME/.inkly/bin/ink.sh" "$@"
LAUNCH

chmod +x "$HOME/.npm-global/bin/ink"

echo "[X] Applying Inkly/Copilot HPC-safe terminal settings…"

# Disable OSC color sequences and broken terminal features
export COPILOT_NO_COLOR=1
export COPILOT_THEME=plain
export NO_COLOR=1

# Try to reduce Copilot noise (may or may not be respected by CLI)
export COPILOT_LOG_LEVEL=none
export COPILOT_DISABLE_USAGE_FOOTER=1

# Persist for future shells (append only if not already present)
if ! grep -q 'Inkly persistent state' "$HOME/.bashrc"; then
cat <<'EOF' >> "$HOME/.bashrc"

# --- Inkly persistent state ---
export INKLY_HOME="$HOME/.inkly"
export COPILOT_CONFIG_DIR="$INKLY_HOME/copilot"

# --- Inkly/Copilot HPC-safe settings ---
export COPILOT_NO_COLOR=1
export COPILOT_THEME=plain
export NO_COLOR=1
export COPILOT_LOG_LEVEL=none
export COPILOT_DISABLE_USAGE_FOOTER=1

EOF
fi


# --- Verification ---
echo
echo "=== Verification ==="
echo "node:      $(node -v)"                            # Show Node version to confirm availability.
echo "npm:       $(npm -v)"                             # Show npm version to confirm availability.
echo "copilot:   $(copilot --version || true)"          # Show Copilot CLI version if present.
echo "inkly:     $(inkly --version || true)"            # Show Inkly wrapper version (proxies Copilot).

echo
echo "Activating Ink function for this shell..."
# This will re-load PATH, nvm, and the HPC-safe env into the current shell
# WITHOUT writing anything new to ~/.bashrc.
source "$HOME/.bashrc" || true

echo
echo "Installation complete — open a new shell or run '. ~/.bashrc' to activate Ink."
echo "Type 'inkly' to log in with GitHub (if you haven't already)."

echo
echo "Try:"
echo "  inkly \"Say hello\""                         # Example of direct Copilot prompt mode.
echo "  ink  \"Write a Slurm sbatch for 4 CPU tasks and 1 GPU on partition gpu for 12h\"" 
