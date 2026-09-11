# HPC / Inkly Project Tasks

This file tracks the current public project state and next work. Detailed machine-specific debugging notes remain private and are not committed here.

## Current baseline

- [x] Personal canonical repository remains `ryanrvargas/hpc-ink-setup`.
- [x] `dev` is the active integration branch.
- [x] Current `dev` baseline: `22d9d5531586c10db07afcf863d8bb9d01d4e1b7` (PR #114 merged).
- [x] Test suite passes: 95 tests.
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
- [x] Confirm a simplified response contract can answer a real queue question using plugin context.

## Current response-contract validation

- [x] Raw Ollama exact-output test returns the requested token exactly.
- [x] Current production prompt was captured from the real `handle_query()` path.
- [x] Current production prompt still produces extra text (`FINAL_OK Hello`) for an exact-output request.
- [x] Simplified production-style contract returns exact output correctly.
- [x] Simplified contract still answers a real queue question using cluster/plugin context.
- [ ] Replace the current verbose response contract with the validated simplified version on a dedicated branch.
- [ ] Add/adjust regression tests for the simplified contract.
- [ ] Run full pytest/Ruff/diff validation.
- [ ] Merge the simplified-contract change only after CI is green.
- [ ] Sync the merged runtime into the installed Inkly copy used for smoke testing.
- [ ] Re-run isolated literal smoke test through the real `ink` command.
- [ ] Re-run real HPC queue smoke test through the real `ink` command.

## Runtime performance

- [x] Profile plugin execution overhead; plugin work is not the primary latency source.
- [x] Time the runtime stages directly; one staged run completed in about 3.9 seconds total.
- [x] Confirm raw Ollama generation can complete in roughly 4-6 seconds for small prompts.
- [ ] Investigate large timing variance in full end-to-end runs (observed runs from roughly 5 seconds to over 30 seconds).
- [ ] Establish a practical latency target and repeatable benchmark before declaring the runtime fully known-good.

## Establish known-good personal `dev`

- [ ] Finish response-contract and latency validation.
- [ ] Record the final known-good `dev` SHA.
- [ ] Confirm clean working tree and passing CI at that SHA.

## Alice Lab sync

- [ ] Add/verify the Alice Lab fork remote locally.
- [ ] Verify write permission to `thealice-lab/hpc-ink-setup`.
- [ ] Push the exact known-good personal `dev` history to the Alice Lab fork.
- [ ] Verify the organization fork matches the intended personal `dev` SHA.
- [ ] Do not merge/reset `main` or bulk-copy stale branches.

## Gaussian documentation integration

Start only after personal `dev` is known-good and the Alice Lab fork is synchronized.

- [ ] Review the latest `gaussian-docs-scraper` state and licensing/ownership boundaries.
- [ ] Verify scraper database/output portability.
- [ ] Define the integration contract between scraper data and Inkly retrieval.
- [ ] Create a dedicated integration branch; do not integrate directly on `dev`.
- [ ] Add provenance, prompt-injection boundaries, score thresholds, context limits, and graceful error handling.
- [ ] Add tests for relevant match, no match, missing/corrupt DB, prompt injection, context limits, and Ollama failures.
- [ ] Validate end-to-end Gaussian documentation retrieval on the HPC environment.

## Deferred cleanup

- [ ] Set explicit Git author name/email for future commits.
- [ ] Review stale personal branches for eventual archival/deletion only after current collaboration work is stable.
- [ ] Investigate any administrator-level Ollama/model instructions only if response behavior remains unexplained after contract simplification.
- [ ] Revisit broader response formatting/code-output rules after correctness and latency are stable.
