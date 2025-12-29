# Inkly
## An AI-Assisted Interface for Slurm-Based HPC Clusters
Inkly is a cluster-aware command-line assistant that integrates GitHub Copilot CLI with Slurm-based HPC environments. It provides a safer, more accessible way for users to generate job scripts, inspect queue state, and understand cluster behavior without requiring deep prior knowledge of Slurm or Linux system internals.

Inkly is designed for real HPC environments with permission restrictions, shared infrastructure, and safety requirements. It does not bypass cluster policies and does not execute destructive operations.

## Overview
High-performance computing systems are powerful but difficult to use correctly. New users often struggle with:

Writing valid sbatch scripts

Requesting appropriate resources

Understanding queue behavior

Debugging failed jobs

Navigating permission restricted environments

Inkly reduces these barriers by adding an AI-assisted layer on top of existing HPC tools, while remaining constrained by cluster rules and administrator intent.

## The Problem Inkly Solves
The Problem Inkly Solves

Most HPC onboarding assumes users already understand:

Slurm flags and partitions

Module systems

Resource limits

Cluster-specific conventions

In practice, this knowledge gap leads to:

Job failures

Over requested resources

Wasted compute time

Frustration for both users and administrators

Inkly addresses this by combining:

Live cluster context

AI-assisted explanation and generation

Guarded execution paths
## Core Design Philosophy

Inkly is built on three principles:

AI assists, it does not replace system rules

Automation must be non-destructive

Cluster behavior must remain transparent

Inkly does not hide Slurm. It explains it.

## How Inkly Works
Inkly wraps GitHub Copilot CLI with cluster-aware shell and Python helpers.

At runtime, Inkly:

Gathers live HPC context (Slurm configuration, modules, OS metadata)

Injects that context into AI prompts

Filters and constrains outputs to safe operations

Presents results in human-readable form

The heavy lifting is intentionally handled by local helpers rather than raw AI-generated shell commands.

## Safety and Guardrails
Inkly is explicitly designed to prevent destructive behavior.

Planned and implemented safeguards include:

Blocking dangerous commands (rm -rf, mass deletion, system edits)

Restricting file access to user-owned paths

Containerized execution via Apptainer

No modification of Slurm configuration or system files

Inkly cannot alter cluster state beyond what the user could already do manually.

## Features
Natural-language sbatch generation using real cluster limits

Readable wrappers around squeue, sinfo, and related tools

Context-aware explanations of job failures

Installer designed for environments without sudo access

Apptainer-based isolation for safer execution

## Installation and Deployment
Inkly is intended to be deployed in user space or via Apptainer.

Deployment goals:

No root access required

Minimal admin involvement

Clear separation between cluster config and tool logic

Cluster-specific values (partitions, modules, paths) are configuration-driven rather than hardcoded.

## Quick Start
Use tester branch to test new features
```bash
git clone https://github.com/ryanrvargas/hpc-ink-setup.git
bash install.sh
inkly
```

Once you've called inkly, go ahead and log into your account using github with the /login command. Then exit with ctrl + c twice

```bash
cd Container
./build.sh
./install.sh
```
## Usage Examples
```bash
ink "Write a Slurm sbatch script for 2 GPU nodes for 24 hours"
```
```bash
ink "Why is my job pending"
```
## Logging and Research Component
Logging and Research Component

Inkly is also designed as a research platform.

Planned logging includes:

User prompts

AI responses

Job submission outcomes

Error patterns over time

Logs are structured for:

Aggregate analysis

Per user tracking

Opt-in pilot studies

The goal is to measure whether AI assistance improves job success rates, efficiency, and user confidence.
## Portability and Cluster Adaptation
Inkly is built to be adaptable beyond a single cluster.

Portability features:

Configuration based cluster metadata

Containerized execution

Minimal assumptions about filesystem layout

This allows other institutions to audit, adapt, and deploy Inkly safely.
## Limitations
Inkly intentionally does not:

Execute privileged commands

Modify cluster configuration

Replace scheduler policies

Guarantee optimal job performance

It is a guidance and assistive tool, not an autonomous agent.
## Future Work
Planned extensions include:

Automated .out / .err analysis

Resource recommendation based on historical jobs

Domain-specific workflow profiles

Safer dry-run validation of job scripts
## Who This Is For
Inkly is for:

Students learning HPC

Researchers onboarding to Slurm

Labs seeking safer AI tooling

Administrators interested in usability research

It is not for:

Bypassing cluster rules

Fully autonomous job control

Production automation without human oversight