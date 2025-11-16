# Ink: HPC AI Assistant

Ink is a one-step setup that installs and configures the **Ink CLI** (powered by GitHub Copilot) for use on **HPC clusters** such as Slurm-based systems.  
It automatically reads your environment (Slurm config, OS info, available modules) and feeds that context into AI prompts.

## Quick Start
Use tester branch to test new features
```bash
git clone https://github.com/ryanrvargas/hpc-ink-setup.git
bash install.sh
```

## Example on how to use ink/inkly
```bash
ink "Write a Slurm sbatch script for 2 GPU nodes for 24 hours"
```
Ink(Copilot) will automatically read your cluster’s slurm.conf, os-release, and available modules to tailor its output.

