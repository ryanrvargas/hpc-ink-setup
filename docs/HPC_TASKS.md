# HPC / Inkly Project Tasks

This file tracks the current public project state and next work. Detailed machine-specific debugging notes remain private and are not committed here.

## Current baseline

- [x] Personal canonical repository remains `ryanrvargas/hpc-ink-setup`.
- [x] `dev` is the active integration branch.
- [x] Current authoritative `dev`: `0ee3af2c11448980792734547c99cb428fff8ce1` (PR #121 merged).
- [x] Functionally validated runtime code baseline remains `28b4077b76d6c6ade7059425d17ea73585ec2add`.
- [x] Test suite passes: 96 tests.
- [x] Ruff lint and format checks pass.
- [x] CI quality workflow covers Python 3.9 and 3.11 plus Ruff checks.

## Completed stabilization work

- [x] Audit personal branches and separate current work from stale/superseded branches.
- [x] Fix date-sensitive jobs/database tests (PR #111).
- [x] Add CI quality baseline with pytest and Ruff (PR #112).
- [x] Fix plugin retrieval defaults so unrelated queries do not fall back to all plugins (PR #113).
- [x] Revise Inkly response contract so literal/non-HPC requests are not automatically reframed as HPC tasks (PR #113).
- [x] Add explicit exact-output instruction to the response contract (PR #114).
- [x] Confirm plugin discovery/retrieval overhead is small relative to model generation.
- [x] Confirm safe retrieval settings preserve relevant HPC plugin selection.
- [x] Test a simplified response contract as a diagnostic; later isolation showed simplification is not required.

## Current response-contract validation

- [x] Raw Ollama exact-output test returns the requested token exactly.
- [x] Capture the exact production prompt from the real `handle_query()` path.
- [x] Confirm the production prompt without a terminal newline can produce extra text (`FINAL_OK Hello`).
- [x] Rule out plugin selection, conversation history, CLI argument handling, and stdout piping as the primary cause.
- [x] Rule out fully piped stdin/stdout/stderr subprocess handling; the wrapper still returned exact output.
- [x] Rule out the wrapped response-contract sentence as the cause.
- [x] Repeat the minimal newline-terminated prompt 5 times; exact output succeeded 5/5.
- [x] Add a terminal newline to the captured branch prompt; exact output succeeded 5/5.
- [x] Add a terminal newline to the original verbose production prompt; exact output succeeded 5/5.
- [x] Supersede the contract-simplification hypothesis; retain the existing production contract.
- [x] Implement exactly one terminal newline in prompt assembly on `fix/prompt-terminal-newline`.
- [x] Add regression coverage requiring one terminal newline.
- [x] Run full pytest/Ruff/diff validation for the terminal-newline fix.
- [x] Run exact-output smoke test through the branch runtime.
- [x] Run real HPC queue smoke test through the branch runtime.
- [x] Commit, push, and merge the terminal-newline fix after validation passes (PR #116).
- [x] Sync the merged runtime into the installed Inkly copy.
- [x] Re-run final literal and HPC smoke tests through the real `ink` command.

## Runtime performance

- [x] Profile plugin execution overhead; plugin work is not the primary latency source.
- [x] Time the runtime stages directly; one staged run completed in about 3.9 seconds total.
- [x] Confirm raw Ollama generation can complete in roughly 4-6 seconds for small prompts.
- [ ] Investigate large timing variance in full end-to-end runs (observed runs from roughly 5 seconds to over 30 seconds).
- [ ] Establish a practical latency target and repeatable benchmark before declaring the runtime fully known-good.

## Establish known-good personal `dev`

- [x] Finish response-contract correctness validation; keep latency optimization tracked separately.
- [x] Record functionally known-good `dev` SHA: `28b4077b76d6c6ade7059425d17ea73585ec2add`.
- [x] Confirm clean local `dev` at the functional baseline and green PR #116 CI before merge.

## Alice Lab sync

- [x] Add/verify the Alice Lab fork remote locally.
- [x] Verify write permission to `thealice-lab/hpc-ink-setup`.
- [x] Push the exact known-good personal `dev` history to the Alice Lab fork.
- [x] Verify the organization fork matches personal `dev` at `0ee3af2c11448980792734547c99cb428fff8ce1`.
- [x] Preserve `main` and avoid bulk-copying stale branches during sync.

## Gaussian documentation integration

The scraper and Inkly are being developed as two components of one system.
Phase 1 uses direct local retrieval. MCP is intentionally deferred until the
direct path is working, tested, and benchmarked.

### Phase 1 — direct scraper-to-Inkly retrieval

- [x] Create dedicated integration branch `integration/gaussian-docs`; do not implement directly on `dev`.

Architecture:

`documentation sources -> scraper -> ~/.inkly/{domain}.db -> standardized retrieval interface -> bounded source-labeled context -> Inkly model -> answer`

- [x] Review the latest `gaussian-docs-scraper` implementation and data model.
- [x] Record that Nathan's scraper work is being integrated as part of the shared HPC/Inkly project while preserving authorship and Git history.
- [x] Choose scraper licensing model: AGPL-3.0-only for open/source-sharing use plus a separate commercial license.
- [ ] Confirm contributor dual-licensing permission/ownership for Nathan's existing scraper contributions. **Blocked on explicit contributor permission.**
- [ ] Add the finalized AGPL/commercial licensing files to the scraper repository. **Blocked until contributor permission is confirmed.**
- [x] Remove machine-specific scraper output paths and make database/output configuration portable across Windows and HPC/Linux.
- [x] Use the shared `inkly-test` virtual environment for Inkly/scraper Phase 1 integration testing on Cuttlefish.
- [x] Make the scraper installable with `python -m pip install -e .` and document the shared-environment setup for Inkly consumers.
- [x] Make the normal Inkly installation path provision/verify the scraper dependency so users do not need to remember separate manual setup steps.
- [ ] Before release, replace the setup script's scraper integration ref with a stable scraper tag/release.
- [x] Define a standardized internal documentation search interface, `search_docs(domain, query, top_k)`, with optional tool/docs-dir parameters.
- [x] Standardize runtime plugin execution as `run(query: str)` while adapting legacy zero-argument cluster plugins without changing their behavior.
- [x] Pass the user's actual query into selected plugin execution; Gaussian retrieval can now consume it in the next integration step.
- [ ] Connect `docs_gaussian` to the scraper's standardized `search_docs(...)` interface and scraper-produced SQLite database, replacing the static Gaussian snippets.
- [x] Keep retrieval local in Phase 1; do not require GitHub Copilot or MCP.
- [ ] Add provenance/source labels to retrieved passages.
- [ ] Treat scraped content as untrusted reference material that cannot override Inkly instructions or the user's request.
- [ ] Add score thresholds, `top_k` limits, context-size limits, and graceful missing/corrupt database handling.
- [ ] Add tests for relevant match, no match, missing/corrupt DB, prompt injection, context limits, and Ollama/backend failures.
- [ ] Validate end-to-end Gaussian documentation retrieval on the HPC environment.
- [ ] Benchmark Phase 1 retrieval and total response latency before introducing a network service.

### Phase 2 — shared knowledge service / interoperability

Begin only after Phase 1 is correct, fast, and stable.

- [ ] Evaluate a shared central knowledge database/service for multiple approved applications or models.
- [ ] Preserve the same standardized documentation-search contract when moving from local SQLite to a shared service.
- [ ] Define authentication, permissions, and networking requirements for remote clients.
- [ ] Evaluate an MCP server as an optional standardized tool layer over the shared knowledge service.
- [ ] Use MCP only if it improves interoperability without unacceptable latency or operational complexity.
- [ ] Keep GitHub Copilot out of the Inkly architecture unless the project explicitly changes direction.

## User-study preparation

Target window from the HPC meeting: November-December 2026.

- [ ] Confirm where user studies may be conducted if they cannot take place at UNCW.
- [ ] Define representative HPC tasks for participants.
- [ ] Define measurements for task completion, answer quality, latency, user confusion, and failure recovery.
- [ ] Add privacy/consent and study-data handling requirements before recruiting participants.
- [ ] Use study results to prioritize usability, retrieval-quality, and latency improvements.

## Deferred cleanup

- [ ] Set explicit Git author name/email for future commits.
- [ ] Review stale personal branches for eventual archival/deletion only after current collaboration work is stable.
- [ ] Investigate any administrator-level Ollama/model instructions only if response behavior remains unexplained after contract simplification.
- [ ] Revisit broader response formatting/code-output rules after correctness and latency are stable.
