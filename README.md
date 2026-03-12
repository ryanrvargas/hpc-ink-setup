## 🐙 Inkly
AI-Assisted Interface for Slurm-Based HPC Clusters

Inkly is a cluster-aware command-line assistant for Slurm-based HPC environments.
It integrates GitHub Copilot CLI with live cluster context and safety guardrails.

Inkly is designed for real HPC environments with shared infrastructure, permission restrictions, and administrative policies.

It does not bypass cluster rules.
It does not execute destructive operations.
It runs entirely in user space.

## 🚀 What This Release Provides

This repository distributes:
- A prebuilt Apptainer/Singularity container (inkly.sif)
- A host-side launcher (Container/inkApp.py)
- A policy-driven runtime (ink_core.py)
- A hardened default configuration (config.toml)
No container build is required.

## 🧱 Runtime Requirements
To use Inkly, a cluster must provide:
- Slurm
- Apptainer or Singularity
- Python 3 on login node
- Outbound internet access (for Copilot API)
- GitHub Copilot CLI authentication on the host
GPU support is optional.
Inkly automatically detects GPU availability and enables --nv only when supported.

## 🔐 Authentication Requirement
Inkly uses GitHub Copilot CLI inside the container but relies on host-side authentication.
Before first use:
```
copilot auth login
```
After successful login:
```
python Container/inkApp.py
```
Inkly will bind the Copilot auth directory into the container securely.

## ⚙️ Quick Start
```
git clone https://github.com/ryanrvargas/hpc-ink-setup.git
cd hpc-ink-setup

python3 Container/inkApp.py "Write a Slurm sbatch script for 2 GPU nodes for 24 hours"
```
No container build required.

## 🧠 How Inkly Works
At runtime, Inkly:
1. Gathers live cluster context:
- sinfo
- OS metadata
- GPU availability
- Slurm configuration hints

2. Injects that context into Copilot prompts.

3.Enforces:
- Prompt filtering
- Shell command deny lists
- Output sanitization

4. Runs Copilot inside a container with minimal host bind exposure.

## 🔒 Security Model
Inkly enforces multiple layers of protection:

### Container Isolation
- --contain --no-home
- Minimal bind mounts
- Optional GPU passthrough
- No root privileges required

### Prompt Filtering
- Blocks destructive intent before reaching Copilot:
- rm
- mv
- chmod
- sudo
- Recursive copy misuse
- Explicit regex checks

### Shell Guardrails
Copilot tool execution is constrained by deny rules defined in config.toml.

### Logging Safety
Raw prompt logging is disabled by default in this release.

##📦 Container Stability
This release:
- Pins GitHub Copilot CLI version
- Pins Node.js version inside container
- Does not auto-upgrade dependencies
- Produces deterministic runtime behavior

Container rebuild is not required for usage.

## 🌍 Supported Environments
Tested against:
- Slurm-based clusters
- Apptainer runtimes
- Singularity runtimes
- CPU-only nodes
- GPU-enabled nodes

Internet access is required for Copilot API calls.
Air-gapped clusters are not supported in this version.

## ⚠ Known Limitations
- Requires outbound internet access.
- Requires user-level Copilot authentication.
- Does not support non-Slurm schedulers.
- Does not function on clusters without container runtime.
- Does not provide offline AI inference.
- Inkly is an assistive interface, not an autonomous scheduler.

## 📊 Logging & Research Mode
Inkly supports structured logging for research evaluation.
By default:
- Prompt logging: enabled (sanitized)
- Raw prompt logging: disabled
- AI response logging: enabled
- Job outcome logging: disabled

Logging behavior is configurable via config.toml.

## 🧪 Validation Criteria for v0.1.0-portable
This release is considered portable when:
- A user on a different Slurm cluster can:
  - Clone repository
  - Run inkApp.py
  - Authenticate Copilot
  - Generate Slurm job scripts
- No container rebuild required
- No GPU requirement
- No unsafe logging defaults
- Works with Apptainer or Singularity

## 🏷 Version
First portable release:
```
v0.1.0-portable
```

## 🧭 Architecture Overview
```
User → inkApp.py → Container (inkly.sif) → ink → ink_core → Copilot CLI
```
Host provides:
- Copilot authentication
- Configuration
- Logging directory

Container provides:
- Node
- Copilot CLI
- Python runtime
- Isolated execution

## 🎯 Who Inkly Is For
- Students learning HPC
- Researchers onboarding to Slurm
- Labs improving job success rates
- Administrators exploring AI-assisted usability
Inkly is not intended for:
- Privilege escalation
- Autonomous job management
- Scheduler replacement
- Production automation without review
