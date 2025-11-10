#!/bin/bash
# HPC-aware wrapper that feeds cluster context automatically from slurm.conf, os-release, software, and module
# Call this function and then a prompt
# ex. "ink 'Write a slurm sbatch script for 2 gpu nodes for 24 hours"

########################To activate it:#############################
# echo "source ~/hpc-ink-setup/ink.sh" >> ~/.bashrc
# source ~/.bashrc

ink() {
  set -o pipefail
  CONTEXT=$(
    {
      echo "===== /etc/slurm/slurm.conf ====="
      cat /etc/slurm/slurm.conf 2>/dev/null || echo "(not readable)"
      echo
      echo "===== /etc/os-release ====="
      cat /etc/os-release 2>/dev/null || echo "(not readable)"
      echo
      echo "===== software ====="
      command -v software >/dev/null && software 2>/dev/null || echo "(software command not found)"
      echo
      echo "===== module avail ====="
      if command -v module >/dev/null 2>&1; then
        module avail 2>&1 || echo "(module system failed)"
      else
        echo "(module not found)"
      fi
      echo
    }
  )
  # Copilot/inkly gets called, then using our variable CONTEXT, so it has background information to create files
  inkly -p "Using the following HPC environment context:
$CONTEXT

Now, $*"
}
