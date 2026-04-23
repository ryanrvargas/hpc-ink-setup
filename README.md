# Inkly

Inkly is a Slurm-aware HPC assistant designed to help users work more efficiently on high performance computing systems.

It combines:
- an Ollama-backed language model
- cluster-aware plugin context
- retrieval-based plugin selection
- persistent conversation history
- job-history analytics

The goal is simple: reduce the time users spend searching for documentation, asking repetitive questions, or manually piecing together cluster context before they can get real work done.

Inkly is designed for command-line use in shared research environments and can be configured to use:
- an admin-managed Ollama command
- a direct Ollama server
- an SSH-tunneled Ollama server
- a local `ollama run` workflow

## What Inkly Does

Inkly helps users interact with an HPC system in a more natural and productive way.

Examples of what it can do:
- explain Slurm usage and queue behavior
- summarize node and partition information
- surface cluster-specific documentation snippets
- provide historical job-intelligence summaries
- use prior conversation context to answer follow-up questions
- route user queries through the most relevant plugins before invoking the model

Inkly is not a scheduler, not an autonomous agent, and not a replacement for cluster policy. It is a retrieval-augmented assistant that helps users work faster and ask better questions.

## Core Features

### 1. Ollama-only backend

Inkly uses Ollama as its model backend.

Supported transport modes:
- `cli_run`
- `direct_host`
- `ssh_tunnel`
- `admin_command`

These modes allow Inkly to work across several deployment patterns, from a local host-side install to a shared admin-managed service.

### 2. Retrieval-based plugin selection

Inkly does not blindly run every plugin for every question.

Instead, it can:
- discover available plugins
- rank them against the user’s query
- execute only the most relevant ones
- assemble their outputs into the final prompt

This helps keep prompts focused and more relevant.

### 3. Persistent conversation history

Inkly stores per-user conversation history and can inject recent context into future prompts.

This improves follow-up questions such as:
- “What about the GPU partition?”
- “Can you explain that again more simply?”
- “Now write the script for that”

Older context can also be summarized when history becomes large.

### 4. Job-history analytics

Inkly can maintain a structured SQLite job-history database and use it for analytics-driven context.

Examples include:
- partition success rates
- memory bucket failure rates
- common failure states
- dataset-size checks before enrichment

This helps Inkly answer questions using actual historical cluster patterns instead of only general advice.

### 5. Interactive terminal response rendering

In interactive terminal use, Inkly can display:
- a loading spinner while waiting for model output
- live character-by-character streaming when output begins

This makes the CLI feel more responsive while still preserving the full response for runtime use.

## Architecture Overview

At a high level, Inkly works like this:

1. The user runs `ink <prompt>`
2. Inkly loads validated configuration from `~/.inkly/config.toml`
3. Runtime components are initialized:
   - conversation manager
   - plugin manager
   - retriever
   - Ollama backend
4. Inkly selects and runs relevant plugins
5. Inkly builds a prompt from:
   - response contract
   - conversation history
   - plugin outputs
   - the current user query
6. Inkly sends the prompt to Ollama
7. The final response is streamed or printed back to the user
8. Conversation history is updated

## Repository Layout

A simplified view of the important pieces:

```text
inkly/
  config.py
  ink_core.py
  db.py
  jobs.py
  llm/
    backend.py
    ollama_tunnel.py
  core/
    runtime.py
    conversation.py
  plugins/
    manager.py
    queue_status.py
    node_info.py
    jobs_summary.py
    docs_gaussian.py
  retrieval/
    retriever.py
    vector_store.py
    classifier.py
    embedding.py

tests/
scripts/
config.toml
install.py
ink
```

## Requirements

### For users

- a Linux environment with Python 3
- access to a Slurm-based cluster
- access to an Ollama service through one of the supported modes
- a working Inkly install under `~/.inkly`

### For admins

- an Ollama installation available on a login node or compute node
- one or more models already pulled and ready to serve
- a deployment pattern chosen for users:
  - `admin_command`
  - `direct_host`
  - `ssh_tunnel`

## Installation for Users

This section covers the normal user-side installation path.

### 1. Clone the repository

```bash
git clone <repo-url>
cd hpc-ink-setup
```

### 2. Run the installer

```bash
python3 install.py
```

The installer will:
- create `~/.inkly`
- install the runtime package under `~/.inkly/lib`
- initialize `~/.inkly/jobs.db`
- install the `ink` launcher into `~/.inkly/bin/ink`
- optionally add `~/.inkly/bin` to your shell `PATH`
- verify the key installed pieces exist

### 3. Reload your shell if needed

If path injection is enabled in the install config:

```bash
source ~/.bashrc
```

### 4. Confirm Inkly runs

```bash
ink hello
```

If configuration and backend routing are correct, Inkly should respond in the terminal.

## Configuration

Inkly loads its runtime settings from:

```text
~/.inkly/config.toml
```

The main config sections are:
- `[install]`
- `[state]`
- `[logging]`
- `[logging.history]`
- `[intelligence]`
- `[conversation]`
- `[core]`
- `[retrieval]`
- `[llm]`
- `[ollama]`

### Example `llm` section

```toml
[llm]
model = "llama3-cuttlefish:latest"
```

### Example `ollama` section

```toml
[ollama]
mode = "admin_command"
command_path = "/opt/ollama/ollama"
command_args = []
tunnel_enabled = false
ssh_target = ""
remote_host = "127.0.0.1"
remote_port = 11434
local_host = "127.0.0.1"
local_port = 11434
startup_timeout_sec = 30
manage_server = false
use_direct_host = false
direct_host = ""
direct_port = 11434
```

## Ollama Deployment Modes

Inkly supports multiple ways to reach an Ollama model.

### 1. `admin_command`

Use this when an admin provides a managed Ollama command on the login node or another shared environment.

Inkly sends prompts through stdin to the configured command path. This avoids command-line length issues and works well for shared, centrally managed deployments.

Use this when:
- admins want users to call a controlled command
- the model runtime should be wrapped in a specific environment
- users should not manage the Ollama process themselves

### 2. `direct_host`

Use this when an Ollama server is already running on a reachable host and port.

Inkly sets `OLLAMA_HOST` and calls `ollama run <model>` against that server.

Use this when:
- the server is already up
- users can connect directly to it
- admins want a shared model endpoint without wrapping the command locally

### 3. `ssh_tunnel`

Use this when the Ollama server is running remotely and should be reached through a local SSH tunnel.

Use this when:
- direct network access is restricted
- users are allowed to tunnel to the model host
- the model runs on another node, such as a GPU node

### 4. `cli_run`

Use this when `ollama run <model>` should execute locally against a local Ollama environment.

This is the simplest mode and is most useful for local development, testing, or single-user setups.

## Admin Setup Guide

This section is for cluster administrators or maintainers who want to provide Inkly-backed model access to users.

### Goal

Make an Ollama model available in a way that cluster users can reach through one of Inkly’s supported transport modes.

### Deployment Pattern A: `admin_command`

This is often the cleanest shared deployment pattern for login-node usage.

#### What admins do

1. Install Ollama in a shared location
2. Pull the models that should be available
3. Provide a wrapper or managed executable path
4. Configure environment variables so service behavior is predictable
5. Point users to the correct `command_path`

#### Example wrapper

```bash
#!/bin/bash

export OLLAMA_KEEP_ALIVE=-1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_QUEUE=1
export CUDA_VISIBLE_DEVICES=""
export OLLAMA_NO_CLOUD=1

exec /opt/ollama/bin/ollama
```

#### What this wrapper does

This wrapper does not start a persistent server by itself. It prepares the runtime environment before the Ollama executable is invoked.

These variables are useful because they shape service behavior:

- `OLLAMA_KEEP_ALIVE=-1` keeps the model loaded instead of unloading it after each request
- `OLLAMA_MAX_LOADED_MODELS=1` limits simultaneous loaded models
- `OLLAMA_NUM_PARALLEL=1` limits parallel generation work
- `OLLAMA_MAX_QUEUE=1` constrains request queueing
- `CUDA_VISIBLE_DEVICES=""` hides GPUs in a CPU-only login-node scenario
- `OLLAMA_NO_CLOUD=1` disables cloud behavior

In practice, admins may use a wrapper like this as part of a larger service setup or managed command path policy.

#### User config for this mode

```toml
[ollama]
mode = "admin_command"
command_path = "/opt/ollama/ollama"
command_args = []
```

If admins expose a different wrapper path, users should point `command_path` to that instead.

### Deployment Pattern B: shared Ollama server on another node

This pattern is useful when the model should run on a GPU node or another dedicated host.

#### What admins do

1. Install Ollama on the serving node
2. Pull the desired model
3. Start the Ollama server
4. Keep the service alive
5. Expose it to users either directly or through SSH tunneling

#### Example server startup idea

The exact startup method depends on local policy, but conceptually the admin needs a persistent Ollama service bound to the desired host and port, usually `11434`.

Users then choose either:
- `direct_host`
- `ssh_tunnel`

#### User config for direct host

```toml
[ollama]
mode = "direct_host"
direct_host = "gpu-node-or-hostname"
direct_port = 11434
```

#### User config for SSH tunnel

```toml
[ollama]
mode = "ssh_tunnel"
ssh_target = "user@gpu-node-or-hostname"
remote_host = "127.0.0.1"
remote_port = 11434
local_host = "127.0.0.1"
local_port = 11434
```

## Conversation History

Inkly stores persistent per-user conversation history under:

```text
~/.inkly/conversations/
```

This allows follow-up questions to make sense without forcing the user to restate earlier context.

Conversation behavior is configured under:

```toml
[conversation]
enabled = true
max_messages = 20
summarize = true
summary_trigger = 30
max_summary_chars = 1200
```

### What these fields mean

- `enabled`: turn conversation persistence on or off
- `max_messages`: how many recent turns to keep directly in prompt context
- `summarize`: whether older context should be compressed
- `summary_trigger`: history length at which summarization begins
- `max_summary_chars`: how large the summary block can become

## Retrieval and Plugin Selection

Inkly can use retrieval to decide which plugins are relevant to a query.

Configured under:

```toml
[retrieval]
enabled = true
top_k = 3
fallback_to_all_plugins = true
min_score = 0.0
index_path = "~/.inkly/retrieval_index.json"
```

### What this means

- `enabled`: whether retrieval-based plugin selection is active
- `top_k`: maximum number of high-ranking plugins to use
- `fallback_to_all_plugins`: whether to fall back if retrieval yields nothing
- `min_score`: minimum score threshold
- `index_path`: where the retrieval index is stored

### Why this matters

Without retrieval, Inkly may run too much context for simple questions.

With retrieval, Inkly can narrow the context to the plugin outputs most likely to matter.

## Built-in Plugin Types

The current design supports plugin discovery and execution through the plugin manager.

Typical plugin categories include:
- queue status
- node and partition information
- job-history summaries
- static cluster documentation snippets

## Building Custom Plugins

Inkly’s plugin system is designed to be simple to extend.

A plugin should:
- live under `inkly/plugins/`
- define `PLUGIN_META`
- provide a `run()` function that returns formatted text

At a high level, `PLUGIN_META` should describe:
- `name`
- `description`
- `category`
- `example_queries`

### Good plugin design principles

- keep output concise
- return clean, formatted text
- avoid side effects
- avoid assuming interactive shell state
- make plugin output useful as prompt context

### Example plugin ideas

- partition availability summaries
- license usage summaries
- cluster-specific software usage notes
- common job failure explanations
- scheduler policy reminders

## Job-History Database and Analytics

Inkly can maintain a structured job-history database in:

```text
~/.inkly/jobs.db
```

This supports analytics-backed context rather than relying only on generic model answers.

### Why this matters

Historical job outcomes can help answer questions like:
- which partitions succeed most often
- whether large-memory jobs fail more frequently
- what failure states are most common
- whether there is enough data to trust enrichment

### Common analytics concepts

- **dataset size**: how many jobs are present in the database
- **partition success rate**: fraction of jobs that completed successfully by partition
- **memory bucket failure rate**: failure rate grouped by requested memory ranges
- **failure distribution**: most common failure states such as `FAILED`, `TIMEOUT`, or `CANCELLED`

These summaries are intended to give users a more grounded picture of cluster behavior.

## Example Usage

### Basic query

```bash
ink hello
```

### Ask about partitions

```bash
ink what partitions are available and which ones have GPUs
```

### Ask about queue state

```bash
ink how busy is the cluster right now
```

### Ask about job behavior

```bash
ink do high-memory jobs fail more often on this cluster
```

### Ask for documentation help

```bash
ink how do I run Gaussian on this cluster
```

## Current Limitations

- Inkly is only as useful as the model, plugins, and cluster context available to it
- model quality depends on the Ollama model selected by the deployment
- plugin coverage determines how cluster-aware the final answers can be
- prompt assembly and truncation behavior may continue to evolve
- shared-service deployment still requires admin setup and operational discipline
- container support is not part of the current documented workflow

## Roadmap Direction

Inkly is moving toward:
- stronger retrieval-augmented HPC assistance
- richer cluster-aware plugins
- improved prompt assembly
- clearer deployment patterns for shared Ollama services

## Contributing

If you want to contribute:
- keep changes aligned with the Ollama-only architecture
- prefer clean, testable Python modules
- avoid reintroducing stale Copilot or Node/NVM assumptions
- update tests and documentation when behavior changes

## Summary

Inkly is a Slurm-aware command-line HPC assistant built around Ollama, retrieval-selected plugin context, conversation history, and job-history analytics.

Its purpose is to help users work faster, reduce friction, and spend less time hunting for answers that the system can surface directly from the command line.
