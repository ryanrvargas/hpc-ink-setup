# HPC / Inkly Project Tasks

This file tracks the current public project state and next work. Detailed machine-specific debugging notes remain private and are not committed here.

## Project goal

Inkly should make HPC/Linux easier for users by allowing them to describe what
they are trying to accomplish and receiving correct, useful guidance for the
HPC system they are actually using.

For Slurm workflows, Inkly should be able to help create usable SBATCH files
grounded in verified information about the current HPC environment. General or
external documentation may supplement that knowledge, but cluster-specific
commands, paths, modules, partitions, resource policies, and other local facts
must not be presented as correct unless they are verified for that cluster.

The goal is not simply to retrieve documentation. The full path must be useful:

`user intent -> verified/relevant knowledge -> Inkly reasoning -> correct HPC guidance or SBATCH file -> successful user task`

## Current baseline

- [x] Personal canonical repository remains `ryanrvargas/hpc-ink-setup`.
- [x] `dev` is the active integration branch.
- [x] Current authoritative `dev`: `d78c58759aa27fda0913e6e185a50c2c496a68ef` (PR #2 merged).
- [x] Current fully validated runtime baseline: `d78c58759aa27fda0913e6e185a50c2c496a68ef`.
- [x] Test suite passes: 118 tests.
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
- [x] Pass the user's actual query into selected plugin execution.
- [x] Connect `docs_gaussian` to the scraper's standardized `search_docs(...)` interface and scraper-produced SQLite database, replacing the static Gaussian snippets.
- [x] Keep retrieval local in Phase 1; do not require GitHub Copilot or MCP.
- [x] Add provenance/source labels to retrieved passages.
- [x] Treat scraped content as untrusted reference material that cannot override Inkly instructions or the user's request.
- [x] Add score thresholds, `top_k` limits, context-size limits, and graceful missing/corrupt database handling.
- [x] Add tests for relevant match, no match, missing/corrupt DB, prompt injection, context limits, and scraper/backend failures covered at the plugin boundary.
- [x] Add a repeatable Phase 1 retrieval benchmark harness for the real `docs_gaussian.run()` path.
- [x] Validate end-to-end Gaussian documentation retrieval on the HPC environment.
- [x] Benchmark Phase 1 retrieval and total response latency before introducing a network service.

### Phase 1B — Cuttlefish Gaussian operational validation

Initial baseline:
- [x] Audit the current Gaussian knowledge database before changing retrieval or adding sources.
- [x] Confirm the current Cuttlefish database contains 3 external sources and 70 passages.
- [x] Run a 10-query realistic Gaussian/HPC retrieval baseline covering submission, SBATCH generation, CPUs, memory, `%mem`, `%nprocshared`, scratch, I/O, restart, and Cuttlefish-specific execution.
- [x] Identify a scheduler-confusion failure: a Slurm submission query ranked an NC State `bsub`/LSF example first.
- [x] Identify weak or missing retrieval coverage for CPU/resource mapping, memory mapping, scratch usage, and restart workflows.
- [x] Confirm that a Cuttlefish-specific query currently retrieves only external-institution documentation.
- [ ] Build a Cuttlefish Gaussian ground-truth validation set before modifying the retrieval architecture.
- [ ] Define source scopes for verified-local, Gaussian-general, external-cluster, and community knowledge.
- [x] Verify Cuttlefish uses Slurm and identify the current partition/resource configuration.
- [x] Verify installed Cuttlefish Gaussian modules and identify `gaussian/avx2/g16_rev_c02` as the default module.
- [x] Test the default Gaussian module instead of assuming that an advertised module is usable.
- [x] Investigate the `g16.profile` permission failure: the Gaussian installation is restricted to the `gaussian` Unix group and the current account is not a member.
- [ ] Verify at least one Gaussian module can actually load and expose a working `g16` executable before constructing the first controlled Gaussian SBATCH job.
- [ ] Confirm the correct process for obtaining Gaussian access/group membership on Cuttlefish.
- [ ] After access is granted, re-run module and executable validation before attempting a Gaussian job.
- [ ] Add an access-aware benchmark case: Inkly must recognize when Gaussian is installed but unavailable to the current user instead of generating a supposedly runnable SBATCH file.



Before considering the Gaussian knowledge path fully validated, verify that
scraper-retrieved information can support correct and useful Gaussian job
creation on the actual Cuttlefish environment.

- [ ] Collect a small set of known-good Gaussian job scripts that previously ran successfully on Cuttlefish.
- [ ] Record the Cuttlefish-specific Gaussian requirements shown by those jobs, including SBATCH directives, executable/module usage, CPU and memory requests, scratch/environment setup, partitions, and input/output handling.
- [ ] Compare scraper-retrieved Gaussian guidance against the known-good Cuttlefish jobs.
- [ ] Classify retrieved guidance as Cuttlefish-verified, generally useful external guidance, conflicting/outdated guidance, or unsupported locally.
- [ ] Test whether Inkly can use the retrieved documentation to produce a reasonable Gaussian SBATCH file without importing commands or policies from another cluster.
- [ ] Compare generated SBATCH files against known-good Cuttlefish examples and document incorrect, missing, or unnecessary directives.
- [ ] Add regression fixtures/tests for verified Cuttlefish Gaussian job patterns and for preventing external-cluster commands from being presented as local commands.
- [ ] Perform non-destructive scheduler/script validation of generated Gaussian job files where supported by the Cuttlefish environment.
- [ ] Run a minimal controlled Gaussian test job on Cuttlefish if permitted, and verify submission, startup, Gaussian execution, and expected output.
- [ ] Record the verified local Gaussian facts separately from external documentation so future Inkly responses can distinguish Cuttlefish-specific knowledge from general examples.
- [ ] Define a repeatable Gaussian job-generation evaluation so future scraper/database changes can be tested against the same known-good cases.

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

- [x] Set explicit Git author name/email for future commits.
- [ ] Review stale personal branches for eventual archival/deletion only after current collaboration work is stable.
- [ ] Investigate any administrator-level Ollama/model instructions only if response behavior remains unexplained after contract simplification.
- [ ] Revisit broader response formatting/code-output rules after correctness and latency are stable.

## 2026-09-28 — Phase 1 install and organization sync

- [x] Revalidate `integration/gaussian-docs` on Cuttlefish: 115 tests passed, Ruff passed, formatting passed, and working tree was clean.
- [x] Compare source `./ink` against installed `ink` and confirm the installed launcher/runtime was stale.
- [x] Back up the existing `~/.inkly` launcher, runtime, config, and databases before reinstalling.
- [x] Reinstall the current validated branch with `python install.py`.
- [x] Verify the normal `ink` command now uses the current installed runtime and matches the safe `./ink` behavior for Cuttlefish-specific Gaussian questions.
- [x] Verify Cuttlefish-specific guarded responses return in about 0.07 seconds instead of falling through to the slow model path.
- [x] Verify `thealice-lab/hpc-ink-setup` contains `main`, `dev`, and `integration/gaussian-docs`.
- [x] Synchronize `integration/gaussian-docs` between the local checkout, personal repository, and Alice Lab organization at `6bba0246`.
- [x] Merge the validated `integration/gaussian-docs` work into Alice Lab `dev` through PR #1 (`8c8ffe36`).
- [x] Validate a fresh install from merged `dev`; users can run `ink` directly without needing `./ink`, and clean installs safely withhold unverified Cuttlefish Gaussian commands.

## 2026-09-28 — Fresh-install Gaussian source-scoping regression

- [x] Merge Alice Lab PR #1 into `dev` at `8c8ffe36b136ab180fe3f0d772d40d408a2bd55f`.
- [x] Sync local `dev` to the merged Alice Lab `dev`.
- [x] Run an isolated fresh install from merged `dev`.
- [x] Verify the fresh-installed `ink` launcher works outside the repository and returns exact `FINAL_OK`.
- [x] Identify a clean-install source-scoping regression when `~/.inkly/gaussian.db` is absent.
- [x] Fix cluster-specific Gaussian handling for missing, corrupt, or empty documentation databases.
- [x] Add regression tests for missing scraper/database, corrupt database, and no-relevant-match clean-install paths.
- [x] Re-run validation: 118 tests passed, Ruff lint passed, Ruff formatting passed, and `git diff --check` passed.
- [x] Repeat isolated fresh-install test with no `gaussian.db`; `ink` safely withheld Cuttlefish Gaussian commands.
- [x] Merge the fresh-install Gaussian source-scoping hotfix through Alice Lab PR #2 (`d78c58759aa27fda0913e6e185a50c2c496a68ef`).
- [x] Personal PR #122 was automatically recognized as merged after the validated Alice Lab `dev` history was synchronized to personal `dev`.
