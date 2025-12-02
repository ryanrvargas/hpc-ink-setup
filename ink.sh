#!/bin/bash
# Ink: HPC-aware assistant built on Inkly (Copilot CLI)
# Usage:  ink "Make me a Slurm sbatch for 2 GPU nodes for 24h"

set -euo pipefail

# --- Detect Inkly binary ---
INKLY_BIN="${HOME}/.npm-global/bin/inkly"
if [ ! -x "$INKLY_BIN" ]; then
  echo "Inkly binary not found — run install.sh first."
  exit 1
fi

# --- Build HPC context with real newlines ---
ctx=""
append() { printf -v ctx '%s%s%s' "$ctx" "$1" $'\n'; }

# Host + OS ---------------------------------------------------------
command -v hostname >/dev/null 2>&1 && append "Hostname: $(hostname)"

if [ -f /etc/os-release ]; then
  os_name=$(grep -m1 '^PRETTY_NAME=' /etc/os-release | cut -d= -f2 | tr -d '"')
  append "OS: ${os_name}"
fi

# SLURM availability ------------------------------------------------
# Per-user queue summary --------------------------------------------
if command -v squeue >/dev/null 2>&1; then
  # Show only a few lines to keep context small.
  append "SLURM Queue (current user: ${USER}):"
  while IFS= read -r line; do
    append "  ${line}"
  done < <(squeue -u "${USER}" -o '%i %t %M %D %R' 2>/dev/null | head -n 10)
fi

# Recent job history via sacct --------------------------------------
if command -v sacct >/dev/null 2>&1; then
  # Last 1 day of history; trim to a few lines.
  append "Recent jobs (sacct, last day):"
  while IFS= read -r line; do
    append "  ${line}"
  done < <(
    sacct -u "${USER}" \
      --format=JobID,State,Elapsed,AllocCPUS,ReqMem \
      -S "$(date -d '1 day ago' '+%Y-%m-%d')" 2>/dev/null \
      | head -n 10
  )
fi

# Module environment -------------------------------------------------
if command -v module >/dev/null 2>&1; then
  # 'module list' is cheaper than 'module avail'; trim header noise.
  append "Loaded modules:"
  # Skip the banner line, keep only a small window of modules.
  module list 2>&1 | sed -n '2,12p' | while IFS= read -r line; do
    append "  ${line}"
  done
fi

[ -f /etc/slurm/slurm.conf ] && append "SLURM Config Path: /etc/slurm/slurm.conf"

# GPU detection -----------------------------------------------------
# Safe: avoids heavy nvidia-smi checks if driver isn't loaded.
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  gpu_line=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -n 1)
  [ -n "$gpu_line" ] && append "GPU: ${gpu_line}"
fi

# Trim empty lines from ctx -----------------------------------------
ctx=$(printf "%s" "$ctx" | sed '/^[[:space:]]*$/d')

# --- Args handling ---
if [ "$#" -eq 0 ]; then
  # Fully interactive mode (preserves Copilot menu UI)
  exec "$INKLY_BIN"
fi

# Safety checks -----------------------------------------------------
prompt_input="$*"

# Prevent dangerous shell-like prompts BEFORE they reach Copilot
if printf '%s' "$prompt_input" | grep -Eiq '\b(rm|mv|unlink|dd|chmod|chown|sudo|rmdir)\b|cp[[:space:]]+-r'; then
  echo "Operation blocked: destructive command detected in prompt."
  exit 1
fi

# Avoid accidental large pastes or binary dumps
if [ "${#prompt_input}" -gt 5000 ]; then
  echo "Input too large (over 5000 chars). Aborting to protect cluster."
  exit 1
fi
if printf '%s' "$prompt_input" | grep -Eq '[[:cntrl:]]'; then
  echo "Input contains control/binary characters — rejecting."
  exit 1
fi

# --- Compose final prompt with real newlines ---
prompt=$'Using the following HPC environment context:\n'"${ctx}"$'\n\nNow: '"${prompt_input}"

echo "===DEBUG CONTEXT START==="
printf '%s\n' "$ctx"
echo "===DEBUG CONTEXT END==="


# --- Call Inkly ---
exec "$INKLY_BIN" -p "$prompt"
