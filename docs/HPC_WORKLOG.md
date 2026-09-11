# HPC / Inkly Worklog

This is a sanitized project worklog for durable collaboration history. Machine-specific paths, credentials, and temporary debugging details are intentionally omitted.

## 2026-09-10 — Repository audit and stabilization

- Audited personal branches and classified them as current, stale, superseded, or unfinished.
- Preserved unfinished repository-assistant work without merging it into `dev`.
- Confirmed the current architecture is Ollama-backed, Slurm-aware, plugin-based, and retrieval-assisted.
- Confirmed Python 3.9 can compile the current source tree.

### PR #111 — Date-relative jobs/database tests

- Replaced stale hard-coded dates in jobs/database flow tests with values relative to the current UTC date.
- Production code was unchanged.
- Result after merge: 95 tests passing.
- Merge SHA: `8f65702e8cf51199297b696c192a4633b07dee0c`.

### PR #112 — CI quality baseline

- Added a `Quality` workflow for pushes and pull requests.
- Test matrix covers Python 3.9 and 3.11.
- Added Ruff lint and format checks.
- Added `ruff.toml` targeting Python 3.9 with a conservative lint rule set.
- Merge SHA: `0f6c7955926357b050204e5e21bdfeff0e234faa`.

## 2026-09-10 to 2026-09-11 — Retrieval and prompt diagnosis

### Retrieval findings

- Profiled plugin discovery/execution and found plugin overhead to be small relative to model generation.
- Found that retrieval accepted zero-score results when `min_score = 0.0` and `fallback_to_all_plugins = true`.
- Verified safer defaults:
  - `min_score = 0.01`
  - `fallback_to_all_plugins = false`
- Verified relevant queries still selected useful plugins such as queue status, node information, and Gaussian documentation.

### Prompt findings

- A fresh conversation did not eliminate slow/irrelevant responses, so stored history was not the primary cause.
- Direct tests showed the assembled response contract itself materially affected output quality and latency.
- A simplified contract produced substantially better literal-instruction behavior while preserving HPC responses.

### PR #113 — Retrieval and response-contract fix

Changes included:

- Safer retrieval defaults in the config template, config dataclass, and retriever constructor.
- A revised response contract that no longer forces unrelated/literal requests into an HPC framing.
- Regression coverage showing unrelated queries can return no plugins.

Validation before merge:

- 95 tests passed.
- Ruff lint passed.
- Ruff format check passed.
- `git diff --check` passed.

Merge SHA: `1ef6b9010ad930bb509d4f0052f0e53669017e60`.

## 2026-09-11 — Installed runtime validation

- Synced the relevant merged runtime files and retrieval settings into the installed Inkly environment used for smoke testing.
- Confirmed the installed retrieval config uses the safer defaults.

### Literal instruction tests

Observed examples:

- Raw Ollama: exact output succeeded in roughly 4-5 seconds.
- Full Inkly: returned `FINAL_OK Hello` instead of exactly `FINAL_OK`, with highly variable latency.
- Staged runtime timing showed one run at about 3.9 seconds total, with model generation dominating and retrieval/history overhead near zero.

Conclusion at this stage:

- Persistent Python/plugin overhead was not the main problem.
- The response contract still influenced exact-output compliance.
- End-to-end latency was variable rather than consistently slow.

### PR #114 — Exact-output instruction

Added an explicit contract rule:

> If the user asks for an exact response, return only the exact requested text and nothing else.

Validation before merge:

- 95 tests passed.
- Ruff lint passed.
- Ruff format check passed.
- Direct experimental contract test returned exact output.

Merge SHA: `22d9d5531586c10db07afcf863d8bb9d01d4e1b7`.

## 2026-09-11 — Post-PR #114 diagnosis

After installing the merged runtime, the real `ink` command still produced `FINAL_OK Hello` and one run took over 30 seconds.

Further isolation ruled out several suspected causes:

- Piping the admin Ollama wrapper through stdout did not reproduce the failure by itself.
- The exact prompt produced by the real `handle_query()` path was captured and tested directly.
- That full production prompt reproduced `FINAL_OK Hello` even when sent straight to Ollama.

This demonstrated that the remaining exact-output issue was caused by the production prompt wording itself, not by installation drift, plugin retrieval, conversation history, CLI argument handling, or stdout piping.

### Simplified production-contract experiment

A shorter contract retained the important rules while removing extra wording around plugin/history context and unavailable cluster information.

Results:

- Literal test: returned exactly `FINAL_OK` in about 5.1 seconds.
- Real HPC validation: answered a queue-status question using cluster/plugin context and reported 14 running jobs.
- The queue answer remained concise and grounded.
- That HPC run took about 18.3 seconds, confirming latency remains variable and should be investigated separately from prompt correctness.

Current conclusion:

1. Simplifying the production response contract is the next correctness change to test and merge.
2. Retrieval behavior is substantially improved.
3. Plugin/runtime overhead is not the primary latency source.
4. End-to-end model/admin-wrapper latency variance remains an open performance issue.
5. `dev` should not yet be declared the final known-good collaboration baseline until the simplified contract and final smoke tests are complete.

## Collaboration sequence after stabilization

Once personal `dev` is known-good:

1. Record the exact known-good SHA.
2. Sync that exact history to `thealice-lab/hpc-ink-setup`.
3. Verify the organization fork matches.
4. Return to `gaussian-docs-scraper`.
5. Integrate scraper-backed Gaussian documentation on a dedicated integration branch rather than directly on `dev`.
