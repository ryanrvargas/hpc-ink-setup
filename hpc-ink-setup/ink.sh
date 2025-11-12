#!/bin/bash
# Ink: HPC-aware assistant built on Inkly (Copilot CLI)
# Lets you type:  ink "Make me a Slurm sbatch for 2 GPU nodes"

set -euo pipefail

# --- Detect Inkly binary ---
INKLY_BIN="${HOME}/.npm-global/bin/inkly"
if [ ! -x "$INKLY_BIN" ]; then
  echo "❌ Inkly binary not found — make sure you’ve run install.sh successfully."
  exit 1
fi

# --- Build HPC context automatically ---
CONTEXT_INFO=""

# Add hostname and OS details
if command -v hostname >/dev/null 2>&1; then
  CONTEXT_INFO+="Hostname: $(hostname)\n"
fi
if [ -f /etc/os-release ]; then
  CONTEXT_INFO+="OS Info: $(grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '\"')\n"
fi

# Include SLURM configuration summary if available
if command -v sinfo >/dev/null 2>&1; then
  CONTEXT_INFO+="SLURM Queues: $(sinfo -h -o '%P %D %C' | head -n 3)\n"
fi
if [ -f /etc/slurm/slurm.conf ]; then
  CONTEXT_INFO+="SLURM Config Path: /etc/slurm/slurm.conf\n"
fi

# Add GPU info if present
if command -v nvidia-smi >/dev/null 2>&1; then
  GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -n 1)
  CONTEXT_INFO+="GPU: $GPU_INFO\n"
fi

# --- Handle no arguments ---
if [ "$#" -eq 0 ]; then
  echo "Usage: ink \"Your HPC prompt here\""
  echo
  echo "Example: ink \"Write a Slurm sbatch file for 4 CPU tasks and 1 GPU\""
  exit 1
fi

# --- Combine context with user query ---
USER_QUERY="$*"
PROMPT="Using the following HPC environment context:\n${CONTEXT_INFO}\n\nNow: ${USER_QUERY}"

# --- Run through Inkly CLI (safe mode retained) ---
"$INKLY_BIN" -p "$PROMPT"
