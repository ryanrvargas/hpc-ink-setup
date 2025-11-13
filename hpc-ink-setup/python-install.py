# Python verision of our install.sh
#!/usr/bin/env python3
"""
Inkly/Ink installer (Python port of install.sh) for a user-space HPC setup.

Actions:
  1) Ensure nvm + latest LTS Node via bash -lc
  2) Configure npm user prefix (~/.npm-global) & PATH
  3) npm i -g @github/copilot
  4) Install safe 'inkly' wrapper (so: inkly "prompt" == copilot -p "prompt")
  5) Install 'ink' launcher that runs your ink.sh with cluster context
  6) Patch ~/.bashrc if its top 'if ! shopt -oq posix; then' lacks a closing 'fi'
"""

import os, sys, shutil, subprocess, re
from pathlib import Path
HOME = Path.home()
BASHRC = HOME / ".bashrc"
NVM_DIR = HOME / ".nvm"
NPM_GLOBAL = HOME / ".npm-global"
BIN_DIR = NPM_GLOBAL / "bin"
INKLY_PATH = BIN_DIR / "inkly"
INK_PATH = BIN_DIR / "ink"
REPO_INK_SH = HOME / "hpc-ink-setup" / "hpc-ink-setup" / "ink.sh"

def run(cmd, env=None, check=True):
    """Run a shell command with visible output."""
    print(cmd)
    cp = subprocess.run(cmd, shell=True, env=env)
    if check and cp.returncode != 0:
        raise SystemExit(cp.returncode)

def bash_login(cmd, env=None, check=True):
    """Run in a login bash so nvm works consistently."""
    return run(f'''bash -lc '{cmd}' ''', env=env, check=check)

def ensure_nvm_and_node():
    print("[1/6] Ensuring Node (nvm) is available (user-space)…")
    node_exists = shutil.which("node") is not None
    if not node_exists and not NVM_DIR.exists():
        print("→ Installing nvm…")
        curl = shutil.which("curl")
        wget = shutil.which("wget")
        if curl:
            run('curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash')
        elif wget:
            run('wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash')
        else:
            print("Error: neither curl nor wget is available — please install one first.", file=sys.stderr)
            sys.exit(1)

    # Install & use latest LTS Node via nvm (always OK to run; idempotent)
    bash_login(f'''
        export NVM_DIR="{NVM_DIR}";
        [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh";
        nvm install --lts;
        nvm use --lts;
        node -v; npm -v
    ''')

def configure_npm_prefix_and_path():
    print("[2/6] Configuring npm for user-space installs…")
    NPM_GLOBAL.mkdir(parents=True, exist_ok=True)

    npmrc = HOME / ".npmrc"
    if npmrc.exists():
        # remove globalconfig/prefix lines (conflict with nvm)
        cleaned = []
        for line in npmrc.read_text().splitlines():
            if not re.match(r'^(globalconfig|prefix)\b', line):
                cleaned.append(line)
        npmrc.write_text("\n".join(cleaned) + ("\n" if cleaned else ""))

    path_line = 'export PATH="$HOME/.npm-global/bin:$PATH"'
    if BASHRC.exists():
        content = BASHRC.read_text()
        if path_line not in content:
            with BASHRC.open("a") as f:
                f.write(path_line + "\n")
    # For current run, prepend now
    os.environ["PATH"] = f"{BIN_DIR}:{os.environ.get('PATH','')}"

def install_copilot_cli():
    print("[3/6] Installing GitHub Copilot CLI via npm…")
    env = os.environ.copy()
    env["NPM_CONFIG_PREFIX"] = str(NPM_GLOBAL)
    # run npm -g install in an nvm-enabled shell
    bash_login(f'''
        export NVM_DIR="{NVM_DIR}";
        [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh";
        npm install -g @github/copilot
    ''', env=env)

def write_file(path: Path, text: str, mode=0o755):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.chmod(path, mode)

def install_inkly_wrapper():
    print("[4/6] Creating secure 'inkly' wrapper…")
    wrapper = r"""#!/bin/bash
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
  --deny-tool 'shell(rm:*)'
  --deny-tool 'shell(sudo:*)'
  --deny-tool 'shell(chmod:*)'
  --deny-tool 'shell(chown:*)'
  --deny-tool 'shell(rmdir:*)'
  --deny-tool 'shell(unlink:*)'
  --deny-tool 'shell(cp:*)'
  --deny-tool 'shell(mv:*)'
)

if [ "$#" -eq 0 ]; then
  exec "$COPILOT_BIN" "${deny_flags[@]}"
fi

case "$1" in
  -*)        exec "$COPILOT_BIN" "$@" "${deny_flags[@]}";;
  help|--help|-h|login|logout|whoami|version|update|suggest|chat|terms)
             exec "$COPILOT_BIN" "$@" "${deny_flags[@]}";;
esac

prompt="$*"
if printf '%s' "$prompt" | grep -Eiq '\b(rm|mv|unlink|dd|chmod|chown|rmdir|sudo)\b|cp[[:space:]]+-r'; then
  echo "❌ Operation blocked: destructive command detected in prompt."
  echo "Inkly runs in safe mode — deleting or modifying files is not allowed."
  exit 1
fi
exec "$COPILOT_BIN" -p "$prompt" "${deny_flags[@]}"
"""
    write_file(INKLY_PATH, wrapper, 0o755)

def install_ink_launcher():
    print("[6/6] Installing ink launcher…")
    # Remove any old “source ink.sh” lines to avoid auto-sourcing at login
    if BASHRC.exists():
        content = BASHRC.read_text()
        new = re.sub(r'.*hpc-ink-setup/ink\.sh.*\n?', '', content)
        if new != content:
            BASHRC.write_text(new)

    if not REPO_INK_SH.exists():
        print(f"Warning: {REPO_INK_SH} not found. The 'ink' launcher will exist but calling it will fail.", file=sys.stderr)

    launcher = f"""#!/bin/bash
exec "{REPO_INK_SH}" "$@"
"""
    write_file(INK_PATH, launcher, 0o755)

def patch_bashrc_missing_fi():
    # Ubuntu often has an opening 'if ! shopt -oq posix; then' at top; if no closing 'fi', add one.
    if not BASHRC.exists():
        return
    txt = BASHRC.read_text()
    if re.search(r'^if ! shopt -oq posix; then', txt, flags=re.M):
        # Count if/fi balance for the leading block
        # Simple heuristic: if file lacks a standalone 'fi' line, append one.
        if not re.search(r'^\s*fi\s*$', txt, flags=re.M):
            print("→ Patching .bashrc: adding missing 'fi' at end of file")
            with BASHRC.open("a") as f:
                f.write("fi\n")

def verification():
    print("\n=== Verification ===")
    bash_login(f'''
        export NVM_DIR="{NVM_DIR}";
        [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh";
        echo -n "node:      "; node -v;
        echo -n "npm:       "; npm -v;
        echo -n "copilot:   "; copilot --version || true;
        echo -n "inkly:     "; inkly --version   || true;
    ''')

def main():
    print("Installing Ink CLI (powered by GitHub Copilot)…")
    ensure_nvm_and_node()
    configure_npm_prefix_and_path()
    install_copilot_cli()
    install_inkly_wrapper()
    install_ink_launcher()
    patch_bashrc_missing_fi()
    # Quietly select current Node (removes old npm prefix warnings); ignore failure
    try:
        bash_login(f'''
            export NVM_DIR="{NVM_DIR}";
            [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh";
            nvm use --delete-prefix "v$(node -v | sed "s/^v//")" --silent
        ''', check=False)
    except Exception:
        pass
    verification()
    print("\nInstallation complete — open a new shell or run:  source ~/.bashrc")
    print('Try:\n  inkly -p "Say hello"\n  ink "Say hello"')

if __name__ == "__main__":
    main()
