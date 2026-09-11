# HPC / Inkly Project Tasks

This file tracks the current public project state and next work. Detailed machine-specific debugging notes remain private and are not committed here.

## Current baseline

- [x] Personal canonical repository remains `ryanrvargas/hpc-ink-setup`.
- [x] `dev` is the active integration branch.
- [x] Current `dev` baseline: `c1a28c6dd568fc8e45a7e0bf189a3deb36c0596d` (PR #115 merged).
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
- [ ] Commit, push, and merge the terminal-newline fix only after validation passes.
- [ ] Sync the merged runtime into the installed Inkly copy.
- [ ] Re-run final literal and HPC smoke tests through the real `ink` command.

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
