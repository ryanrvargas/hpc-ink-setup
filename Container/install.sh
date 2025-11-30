#!/bin/bash
# Inkly CLI installer for container use
# - Installs Node via nvm into $HOME/.nvm
# - Configures npm global prefix at $HOME/.npm-global
# - Installs GitHub Copilot CLI globally
# - Creates an 'inkly' wrapper with HPC-safe defaults
# - Optionally creates an 'ink' launcher if ink.sh is present

set -eo pipefail

# Ensure HOME is set correctly (in container %post this is /opt/inkhome)
HOME="${HOME:-/opt/inkhome}"
export HOME

# Paths inside the container "home"
export NVM_DIR="$HOME/.nvm"
export PATH="$HOME/.npm-global/bin:$PATH"

echo "Installing Inkly (GitHub Copilot CLI environment) into $HOME"
echo

########################################
# [1/4] Install Node via nvm if needed #
########################################

echo "[1/4] Ensuring Node (nvm) is available in user space..."

if ! command -v node >/dev/null 2>&1; then
  echo "  Node not found - installing nvm and Node LTS into $NVM_DIR"

  if [ ! -d "$NVM_DIR" ]; then
    echo "  Downloading nvm..."
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    else
      echo "Error: neither curl nor wget is available for nvm install." >&2
      exit 1
    fi
  fi

  # Load nvm and install Node LTS
  if [ -f "$NVM_DIR/nvm.sh" ]; then
    # Avoid nounset issues inside nvm scripts
    set +u
    . "$NVM_DIR/nvm.sh"
    echo "  Installing latest LTS Node..."
    nvm install --lts
    nvm use --lts
    set -u || true 2>/dev/null || true
  else
    echo "Error: nvm.sh not found at $NVM_DIR/nvm.sh after install." >&2
    exit 1
  fi
else
  echo "  Node detected: $(node -v)"
fi

# Make sure nvm environment is loaded for the rest of the script
if [ -f "$NVM_DIR/nvm.sh" ]; then
  set +u
  . "$NVM_DIR/nvm.sh"
  set -u || true 2>/dev/null || true
fi

###########################################
# [2/4] Configure npm global install path #
###########################################

echo
echo "[2/4] Configuring npm prefix in $HOME/.npm-global..."

mkdir -p "$HOME/.npm-global"

# Clean conflicting prefix/globalconfig from .npmrc if present
if [ -f "$HOME/.npmrc" ]; then
  grep -Ev '^(globalconfig|prefix)' "$HOME/.npmrc" > "$HOME/.npmrc.tmp" || true
  mv "$HOME/.npmrc.tmp" "$HOME/.npmrc"
fi

# Use env var prefix to avoid nvm prefix warnings
export NPM_CONFIG_PREFIX="$HOME/.npm-global"

# Ensure ~/.npm-global/bin is in PATH for future shells
if ! echo "$PATH" | grep -q "$HOME/.npm-global/bin"; then
  export PATH="$HOME/.npm-global/bin:$PATH"
fi

################################
# [3/4] Install Copilot and wrapper #
################################

echo
echo "[3/4] Installing GitHub Copilot CLI with HPC-safe wrapper..."

npm install -g @github/copilot

COPILOT_BIN="$HOME/.npm-global/bin/copilot"
if [ ! -x "$COPILOT_BIN" ]; then
  echo "Error: Copilot CLI not found at $COPILOT_BIN after npm install." >&2
  exit 1
fi

mkdir -p "$HOME/.npm-global/bin"

# Create 'inkly' wrapper
cat <<'EOF' > "$HOME/.npm-global/bin/inkly"
#!/bin/bash
set -euo pipefail

# Runtime HOME is expected to be /opt/inkhome inside container
COPILOT_BIN="$HOME/.npm-global/bin/copilot"

if [ ! -x "$COPILOT_BIN" ]; then
  echo "Error: GitHub Copilot CLI not found at $COPILOT_BIN" >&2
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

clean_output() {
  sed -e '/^Total usage est:/,/^Usage by model:/d' \
      -e '/^Usage by model:/d' \
      -e '/^[[:space:]]*claude-.*Premium request)/d'
}

# No args: interactive Copilot, do not pipe through clean_output
if [ "$#" -eq 0 ]; then
  exec "$COPILOT_BIN" "${deny_flags[@]}"
fi

case "$1" in
  -*)
    exec "$COPILOT_BIN" "$@" "${deny_flags[@]}" ;;
  help|--help|-h|login|logout|whoami|version|update|terms)
    exec "$COPILOT_BIN" "$@" "${deny_flags[@]}" ;;
esac

prompt="$*"

# Block obviously dangerous prompts
if printf '%s' "$prompt" | grep -Eiq '\b(rm|mv|unlink|dd|chmod|chown|rmdir|sudo)\b|cp[[:space:]]+-r'; then
  echo "Operation blocked: destructive command detected in prompt."
  exit 1
fi

# Prompt mode with cleaned output
"$COPILOT_BIN" -p "$prompt" "${deny_flags[@]}" 2>&1 | clean_output
exit $?
EOF

chmod +x "$HOME/.npm-global/bin/inkly"

##########################################
# [4/4] Optional 'ink' launcher for ink.sh #
##########################################

echo
echo "[4/4] Setting up optional 'ink' launcher if ink.sh is present..."

# If an ink.sh script is present next to install.sh inside container, wire it up
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$INSTALL_DIR/ink.sh" ]; then
  chmod +x "$INSTALL_DIR/ink.sh" || true
  cat <<LAUNCH > "$HOME/.npm-global/bin/ink"
#!/bin/bash
exec "$INSTALL_DIR/ink.sh" "\$@"
LAUNCH
  chmod +x "$HOME/.npm-global/bin/ink"
  echo "  'ink' launcher installed to $HOME/.npm-global/bin/ink"
else
  echo "  No ink.sh found at $INSTALL_DIR/ink.sh - skipping 'ink' launcher."
fi

########################################
# HPC-safe environment hints (optional) #
########################################

# You can also hardwire these in %environment in the .def, but they do not hurt here.
if [ -f "$HOME/.bashrc" ]; then
  if ! grep -q 'Inkly/Copilot HPC-safe settings' "$HOME/.bashrc"; then
    cat <<'EOF' >> "$HOME/.bashrc"

# Inkly/Copilot HPC-safe settings
export COPILOT_NO_COLOR=1
export COPILOT_THEME=plain
export NO_COLOR=1
export COPILOT_LOG_LEVEL=none
export COPILOT_DISABLE_USAGE_FOOTER=1

EOF
  fi
fi

unset NPM_CONFIG_PREFIX || true

echo
echo "=== Verification ==="
echo "HOME:      $HOME"
echo "node:      $(node -v || echo 'not found')"
echo "npm:       $(npm -v || echo 'not found')"
echo "copilot:   $("$COPILOT_BIN" --version || echo 'not available')"
echo "inkly:     $("$HOME/.npm-global/bin/inkly" --version 2>/dev/null || echo 'inkly wrapper ready')"

echo
echo "Installation finished inside container image."
echo "At runtime you can use:"
echo "  inkly -p \"Say hello\""
echo "  ink \"Write a Slurm sbatch for gpu partition\"  (if ink.sh was provided)"
