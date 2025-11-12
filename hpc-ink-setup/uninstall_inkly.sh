# uninstall_inkly.sh
#!/bin/bash
# Inkly / Copilot CLI full uninstall (user-space cleanup)
# Removes: nvm, npm-global, Copilot (npm + binary), inkly alias/wrapper,
#          deny-list config, PATH + source lines in .bashrc/.zshrc, npmrc prefixes.
# Auto-fix line endings if CRLF snuck in
if file "$0" | grep -q "CRLF"; then
  echo "Converting Windows line endings to Unix (LF)..."
  sed -i 's/\r$//' "$0"
  exec bash "$0" "$@"
  exit 0
fi

set -eo pipefail

echo "=== Inkly/Copilot UNINSTALL (user-space) ==="

# [0] Shell targets (bash + zsh in case user switched)
SHELL_FILES=("$HOME/.bashrc" "$HOME/.zshrc")

# [1] Back up dotfiles we may edit
echo "[1/7] Backing up dotfiles..."
ts="$(date +%Y%m%d-%H%M%S)"
for f in "${SHELL_FILES[@]}"; do
  [ -f "$f" ] && cp -f "$f" "$f.bak.$ts" || true
done
[ -f "$HOME/.npmrc" ] && cp -f "$HOME/.npmrc" "$HOME/.npmrc.bak.$ts" || true

# [2] Uninstall Copilot CLI (npm) if present
echo "[2/7] Removing Copilot CLI (npm global) if installed..."
if command -v npm >/dev/null 2>&1; then
  npm uninstall -g @github/copilot >/dev/null 2>&1 || true
fi

# [3] Remove user-space install trees
echo "[3/7] Deleting user-space install dirs..."
rm -rf "$HOME/.npm-global" \
       "$HOME/.copilot" \
       "$HOME/.config/github-copilot" \
       "$HOME/.nvm" \
       "$HOME/.npm" \
       "$HOME/.cache"

# [4] Scrub lines we added to rc files (.bashrc/.zshrc)
echo "[4/7] Cleaning PATH + source lines from rc files..."
for f in "${SHELL_FILES[@]}"; do
  [ -f "$f" ] || continue
  # Remove our npm-global PATH export
  sed -i '/export PATH="\$HOME\/\.npm-global\/bin:\$PATH"/d' "$f"
  # Remove ink wrapper sourcing lines (any variant)
  sed -i '/source .*hpc-ink-setup\/hpc-ink-setup\/ink\.sh/d' "$f"
  sed -i '/source ~\/hpc-ink-setup\/hpc-ink-setup\/ink\.sh/d' "$f"
  # Remove typical nvm lines added by the installer
  sed -i '/NVM_DIR=.*\.nvm/d' "$f"
  sed -i '/\[ -s "\$NVM_DIR\/nvm\.sh" \] && \. "\$NVM_DIR\/nvm\.sh"/d' "$f"
  sed -i '/\[ -s "\$NVM_DIR\/bash_completion" \] && \. "\$NVM_DIR\/bash_completion"/d' "$f"
  # Any leftover "nvm use --delete-prefix" helpers
  sed -i '/nvm use --delete-prefix/d' "$f"
done

# [5] Clean ~/.npmrc of incompatible keys
echo "[5/7] Stripping npmrc prefix/globalconfig..."
if [ -f "$HOME/.npmrc" ]; then
  grep -Ev '^(prefix|globalconfig)\b' "$HOME/.npmrc" > "$HOME/.npmrc.tmp" || true
  mv -f "$HOME/.npmrc.tmp" "$HOME/.npmrc"
  # If file is now empty, remove it
  [ -s "$HOME/.npmrc" ] || rm -f "$HOME/.npmrc"
fi

# [6] Kill any current-shell helpers (best effort)
echo "[6/7] Clearing current shell state..."
hash -r || true
unset -f ink 2>/dev/null || true
unset NVM_DIR NPM_CONFIG_PREFIX || true

# [7] Final checks
echo "[7/7] Verifying removals..."
for cmd in copilot inkly node npm; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "→ STILL FOUND: $cmd at $(command -v "$cmd")"
  else
    echo "→ OK: $cmd not found"
  fi
done

echo
echo "Uninstall complete."
echo "Open a NEW terminal (or run: exec \$SHELL -l) before testing a fresh install."

#exec $SHELL -l            # reload a clean login shell