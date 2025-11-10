# Ink: HPC AI Assistant

Ink is a one-step setup that installs and configures the **Ink CLI** (powered by GitHub Copilot) for use on **HPC clusters** such as Slurm-based systems.  
It automatically reads your environment (Slurm config, OS info, available modules) and feeds that context into AI prompts.

## Quick Start

```bash
git clone https://github.com/ryanrvargas/hpc-ink-setup.git
cd hpc-ink-setup/hpc-ink-setup
bash install.sh
```

## Activating the wrapper
Use this:
```bash
echo "source ~/hpc-ink-setup/hpc-ink-setup/ink.sh" >> ~/.bashrc
source ~/.bashrc
```

## Example on how to use ink
```bash
ink "Write a Slurm sbatch script for 2 GPU nodes for 24 hours"
```
Ink(Copilot) will automatically read your cluster’s slurm.conf, os-release, and available modules to tailor its output.

## Add this to your ~/.bashrc
```bash
source ~/hpc-ink-setup/hpc-ink-setup/ink.sh
```
And to reload your shell use this command
