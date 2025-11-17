#!/bin/bash
# Inkly CLI Installer for HPC (user-space, no sudo)
# Installs Node via nvm if missing (using curl or wget)
# Configures npm for a home-local prefix (~/.npm-global) without nvm conflicts
# Installs GitHub Copilot CLI globally (to ~/.npm-global/bin)
# Creates an 'inkly' alias (symlink) to the 'copilot' binary
# Sources Ink wrapper function (ink.sh) for the current user
# Verifies setup at the end
# For testing


# --- CRLF self-fix ---
if file "$0" | grep -q "CRLF"; then          # Detect Windows line endings so Bash won’t choke.
  echo "Converting Windows line endings to Unix (LF)..."
  sed -i 's/\r$//' "$0"                      # Strip carriage returns in place.
  exec bash "$0" "$@"                        # Re-exec the now-fixed script.
fi

set -eo pipefail                              # Exit on error and fail a pipeline if any command fails.

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

  (                                           # Use a subshell so nvm env tweaks don’t leak if set -u later.
    set +u                                    # Loosen undefined-var checks for nvm’s scripts.
    export NVM_DIR="$HOME/.nvm"               # Tell nvm where it lives.
    . "$NVM_DIR/nvm.sh"                       # Load nvm into the shell.
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
COPILOT_BIN="$(command -v copilot || true)"   # Locate the Copilot binary we just installed.
if [ -z "$COPILOT_BIN" ]; then
  echo "Error: Copilot CLI not found after npm install." >&2
  exit 1
fi

mkdir -p "$HOME/.npm-global/bin"              # Ensure the bin dir for our wrapper exists.

# Generate the inkly wrapper script that safely fronts Copilot.
cat <<'EOF' > "$HOME/.npm-global/bin/inkly"
#!/bin/bash
# Inkly secure wrapper — supports both:
#   inkly "prompt here"        -> copilot -p "prompt here"
#   inkly --flag … / subcmd …  -> copilot <as-is>
set -euo pipefail

COPILOT_BIN="$(command -v copilot || true)"
if [ -z "$COPILOT_BIN" ]; then
  echo "Error: GitHub Copilot CLI not found." >&2
  exit 1
fi

deny_flags=(
  --deny-tool 'shell(rm:*)'      # Disallow deletion commands.
  --deny-tool 'shell(sudo:*)'    # Disallow privilege escalation.
  --deny-tool 'shell(chmod:*)'   # Disallow permission changes.
  --deny-tool 'shell(chown:*)'   # Disallow ownership changes.
  --deny-tool 'shell(rmdir:*)'   # Disallow directory removal.
  --deny-tool 'shell(unlink:*)'  # Disallow file unlinking.
  --deny-tool 'shell(cp:*)'      # Disallow copying (conservative default).
  --deny-tool 'shell(mv:*)'      # Disallow moving/renaming (conservative default).
)


# No arguments -> interactive copilot with deny flags
if [ "$#" -eq 0 ]; then
  exec "$COPILOT_BIN" "${deny_flags[@]}"      # Drop into Copilot CLI interactive with guardrails.
fi

# If first token looks like a flag/subcommand, pass-through (keeps existing workflows)
case "$1" in
  -*)        exec "$COPILOT_BIN" "$@" "${deny_flags[@]}";;  # Forward flags directly to Copilot.
  help|--help|-h|login|logout|whoami|version|update|suggest|chat|terms)
             exec "$COPILOT_BIN" "$@" "${deny_flags[@]}";;  # Allow common subcommands unchanged.
esac

# Otherwise, treat the whole argument list as a natural-language prompt
prompt="$*"                                    # Combine args into a single prompt string.

# Extra safety filter against destructive requests in the prompt text
if printf '%s' "$prompt" | grep -Eiq '\b(rm|mv|unlink|dd|chmod|chown|rmdir|sudo)\b|cp[[:space:]]+-r'; then
  echo "Operation blocked: destructive command detected in prompt."
  echo "Inkly runs in safe mode — deleting or modifying files is not allowed."
  exit 1
fi

# Call copilot with -p and our deny flags
exec "$COPILOT_BIN" -p "$prompt" "${deny_flags[@]}"   # Use -p mode so natural text runs as a prompt.
EOF

chmod +x "$HOME/.npm-global/bin/inkly"        # Make the wrapper executable.

# [5/5] Install "ink" launcher (auto-detect repo path)
echo "[5/5] Installing ink launcher…"

# Determine where install.sh actually lives
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

# Ensure ink.sh is executable
chmod +x "$INSTALL_DIR/ink.sh" 2>/dev/null || true

mkdir -p "$HOME/.npm-global/bin"
cat <<LAUNCH > "$HOME/.npm-global/bin/ink"
#!/bin/bash
exec "$INSTALL_DIR/ink.sh" "\$@"
LAUNCH

chmod +x "$HOME/.npm-global/bin/ink"

echo "[X] Applying Inkly/Copilot HPC-safe terminal settings…"

# Disable OSC color sequences and broken terminal features
export COPILOT_NO_COLOR=1
export COPILOT_THEME=plain
export NO_COLOR=1

# Silence Copilot usage logs / footer spam
export COPILOT_LOG_LEVEL=none

# Persist for future shells
cat <<'EOF' >> "$HOME/.bashrc"

# --- Inkly/Copilot HPC-safe settings ---
export COPILOT_NO_COLOR=1
export COPILOT_THEME=plain
export NO_COLOR=1
export COPILOT_LOG_LEVEL=none
EOF


# --- Verification ---
echo
echo "=== Verification ==="
echo "node:      $(node -v)"                            # Show Node version to confirm availability.
echo "npm:       $(npm -v)"                             # Show npm version to confirm availability.
echo "copilot:   $(copilot --version || true)"          # Show Copilot CLI version if present.
echo "inkly:     $(inkly --version || true)"            # Show Inkly wrapper version (proxies Copilot).

echo
echo "Installation complete — open a new shell or run 'source ~/.bashrc' to activate Ink."

echo
echo "Try:"
echo "  inkly -p \"Say hello\""                         # Example of direct Copilot prompt mode.
echo "  ink  \"Say hello\""                             # Example using the HPC-aware wrapper.

echo
echo "Activating Ink function for this shell..."
source ~/.bashrc                                       # Load PATH changes in the current session.
echo "Type 'inkly' and log in with GitHub."


# --- Refresh parent shell environment for immediate use ---
echo
echo "Reloading environment so Node and Inkly are active now..."
exec bash -l                                           # Start a login shell so PATH/nvm are fully applied.
