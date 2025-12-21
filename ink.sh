#!/bin/bash
# Ink: HPC-aware assistant built on Inkly (Copilot CLI)
# Usage:  ink "Make me a Slurm sbatch for 2 GPU nodes for 24h"

set -euo pipefail

# --- Detect Inkly binary ---
INKLY_BIN="${HOME}/.npm-global/bin/inkly"
if [ ! -x "$INKLY_BIN" ]; then
  echo "❌ Inkly binary not found — run install.sh first."
  exit 1
fi

# --- Build HPC context with real newlines ---
ctx=""
append() { printf -v ctx '%s%s%s' "$ctx" "$1" $'\n'; }

command -v hostname >/dev/null 2>&1 && append "Hostname: $(hostname)"
if [ -f /etc/os-release ]; then
  os_name=$(grep -m1 '^PRETTY_NAME=' /etc/os-release | cut -d= -f2 | tr -d '"')
  append "OS: ${os_name}"
fi
if command -v sinfo >/dev/null 2>&1; then
  # Partition name, node count, CPU alloc/idle/other/total (compact)
  append "SLURM Queues (top):"
  sinfo -h -o '%P %D %C' | head -n 3 | while read -r line; do append "  ${line}"; done
fi
[ -f /etc/slurm/slurm.conf ] && append "SLURM Config Path: /etc/slurm/slurm.conf"
if command -v nvidia-smi >/dev/null 2>&1; then
  gpu_line=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -n 1 || true)
  [ -n "${gpu_line:-}" ] && append "GPU: ${gpu_line}"
fi

# --- Args handling ---
if [ "$#" -eq 0 ]; then
  echo 'Usage: ink "Your HPC prompt here"'
  echo 'Example: ink "Write a Slurm sbatch for 4 CPU tasks and 1 GPU on partition gpu for 12h"'
  exit 1
fi

# --- Compose prompt (true newlines) and call inkly ---
prompt=$'Using the following HPC environment context:\n'"${ctx}"$'\nNow: '"$*"
exec "$INKLY_BIN" -p "$prompt"