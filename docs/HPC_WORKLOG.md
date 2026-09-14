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

## 2026-09-11 — Terminal-newline isolation

Further testing overturned the earlier conclusion that the response contract itself needed to be simplified.

### Branch-runtime failure

A source-runtime smoke test using the simplified contract still returned:

`FINAL_OK Hello`

and one run took about 41.6 seconds.

This showed that contract simplification alone did not explain the production behavior.

### Transport isolation

The admin Ollama wrapper was then launched using the same subprocess shape as Inkly, with stdin, stdout, and stderr all piped.

Result:

- Return code: 0
- Output: exactly `FINAL_OK`
- Runtime: about 6.5 seconds

This ruled out the fully piped subprocess transport as the cause.

### Exact prompt comparison

The real branch-generated prompt was captured and compared with the successful manual prompt.

The meaningful differences were:

- one response-contract sentence was wrapped across two lines in the generated prompt
- the generated prompt did not end with a newline

Changing only the wrapped sentence to one line did not fix the issue; the result was still `FINAL_OK Hello`.

This ruled out line wrapping as the cause.

### Terminal-newline tests

The minimal production prompt, which ends with a newline, was executed five times.

Results:

- exact output succeeded 5/5
- runtimes were roughly 3.1 to 5.0 seconds

Next, exactly one terminal newline was added to the captured branch-generated prompt without otherwise changing the prompt.

Results:

- exact output succeeded 5/5
- runtimes were roughly 3.1 to 5.0 seconds

Finally, exactly one terminal newline was added to the original verbose production prompt from the real `handle_query()` path.

Results:

- exact output succeeded 5/5
- runtimes were roughly 3.3 to 5.3 seconds

### Revised conclusion

The evidence strongly indicates that the admin Ollama wrapper/model path is sensitive to whether the prompt is terminated by a newline.

The earlier response-contract simplification hypothesis is therefore superseded. The existing production contract should remain intact.

The next fix is intentionally small:

1. make `assemble_prompt()` return a prompt ending in exactly one newline
2. add regression coverage for the terminal newline
3. validate exact-output and real HPC behavior before merging
4. continue treating large latency variance as a separate performance issue

### Branch-runtime validation after terminal-newline fix

The actual source runtime was tested with the newline fix in place.

Exact-output test:

- Query: `Reply with exactly: FINAL_OK`
- Streamed output: exactly `FINAL_OK`
- Returned response: exactly `FINAL_OK`
- Runtime: about 4.0 seconds

Real HPC queue test:

- Query: `What jobs are running in the queue right now?`
- Response used real queue/plugin context
- Reported 14 running jobs at test time
- Response remained concise and did not invent commands or unrelated advice
- Runtime: about 7.4 seconds

Conclusion:

The terminal-newline fix now passes both literal exact-output behavior and real HPC plugin-context behavior through the actual branch runtime.

## 2026-09-11 — Final installed runtime validation

After merging PR #116, the installed Inkly runtime was synchronized with `dev`.

Final real `ink` tests:

- Exact-output query returned exactly `FINAL_OK`.
- Exact-output runtime: about 30.6 seconds.
- Queue query returned a grounded response reporting 14 running jobs at test time.
- Queue-query runtime: about 7.9 seconds.

Conclusion:

- Prompt correctness is functionally validated.
- Retrieval/plugin behavior is working.
- `28b4077b76d6c6ade7059425d17ea73585ec2add` is the functionally known-good baseline.
- End-to-end latency variance remains an open performance issue.

## 2026-09-14 — Alice Lab dev synchronization

The Alice Lab fork remote was verified and personal `dev` was pushed to the organization fork without modifying `main` or copying stale branches.

Verification:

- Personal remote: `origin/dev`
- Alice Lab remote: `alice/dev`
- Both resolved to `ed0de023c7e27dbdbfadfec9589912f87cfaab81`
- The functionally validated Inkly code baseline remains `28b4077b76d6c6ade7059425d17ea73585ec2add`
- The later `ed0de02...` history includes the runtime-validation tracking update
- Alice Lab `main` was left untouched

The Alice Lab synchronization prerequisite is now complete. The next tracked phase is Gaussian documentation integration.

## 2026-09-14 — Gaussian/Inkly integration architecture

The project direction was clarified after reviewing HPC meeting notes.

Phase 1 will use direct local retrieval rather than MCP:

documentation sources -> scraper -> ~/.inkly/{domain}.db -> standardized retrieval interface -> bounded source-labeled context -> Inkly model -> answer

Decisions:
- Inkly and the scraper are two components of the same overall HPC assistant system.
- GitHub Copilot is not part of the planned architecture.
- The scraper-produced SQLite databases are the initial knowledge source.
- Inkly should retrieve only passages relevant to the current user query.
- A standardized internal documentation-search interface will separate Inkly from the underlying storage implementation.
- Scraped content will be treated as untrusted reference material and will carry provenance.
- Phase 1 must be benchmarked for retrieval and end-to-end latency before adding another server layer.

Future Phase 2:
- Evaluate a shared central knowledge database/service.
- Allow multiple approved models or applications to use the same knowledge if practical.
- Define a standardized network tool/API.
- Evaluate MCP as an optional interoperability wrapper rather than a Phase 1 dependency.
- Define authentication and permissions before supporting remote clients.

User-study planning:
- Tentative target is November-December 2026.
- Study location may need to be outside UNCW.
- The study should measure real HPC task completion, answer quality, latency, confusion, and failure recovery.

Licensing:
- The scraper currently lacks an explicit license.
- Nathan's authorship and Git history should be preserved.
- An explicit license should be selected before the projects are distributed as one product, with terms matching the desired commercial/source-sharing policy.

## 2026-09-14 — Licensing direction

Selected licensing direction for the combined Inkly/scraper system:

- AGPL-3.0-only for open/source-sharing use.
- A separate commercial license for organizations that want proprietary use without AGPL obligations.
- Preserve Nathan's authorship and Git history.
- Confirm contributor ownership/relicensing permission before representing that one person can issue proprietary licenses for all existing scraper contributions.

Engineering integration can continue while that contributor-rights confirmation is documented.

## 2026-09-14 — Scraper portability milestone

Completed the first Phase 1 scraper engineering change on `thealice-lab/gaussian-docs-scraper` branch `integration/inkly-phase1`.

Changes:
- Removed the committed Nathan-specific Windows database output path from `configs/gaussian.toml`.
- Kept the portable default at `~/.inkly/{domain}.db` through `Path.home()`.
- Added `expanduser()` handling so explicit `~` paths resolve correctly.
- Stopped serializing the default output path into generated TOML, avoiding machine-specific absolute paths; custom paths are still preserved.
- Added regression tests for tilde expansion, default-path omission, and custom-path preservation.

Validation:
- Targeted config suite: 26 tests passed.
- Full scraper suite: 151 tests passed.
- `git diff --check` passed.
- `python -m pip check` reported no broken requirements.
- Phase 1 development/testing on Cuttlefish uses the same `inkly-test` virtual environment for Inkly and the scraper.

Scraper commit: `884cdb7f6f064c2255334ddedeb32ac8a9dd3be7` (`Make scraper output paths portable`).

## 2026-09-14 — Standardized documentation search interface

Completed the next Phase 1 scraper milestone on `thealice-lab/gaussian-docs-scraper` branch `integration/inkly-phase1`.

Changes:
- Added `gaussian_scraper.search.search_docs(domain, query, top_k=5, ...)` as the stable internal documentation-search boundary.
- Kept `PassageIndex`, TF-IDF ranking, and SQLite loading behind that interface so Inkly does not need to depend on scraper retrieval internals.
- Updated the existing `search_docs.py` CLI to call the standardized interface.
- Added focused tests covering a real SQLite-backed search and the missing-domain failure path.

Validation:
- Focused search/index tests: 12 tests passed.
- Full scraper suite: 153 tests passed.
- `git diff --check` and staged diff checks passed before commit.

Scraper commit: `71a9c011cd91c5e1fdff005bf942608771940ee9` (`Add standardized documentation search interface`).

## 2026-09-14 — Scraper package installation setup

Made the scraper consumable as a normal Python package for local Phase 1 Inkly integration.

Changes:
- Added `setup.py` with Python 3.9+ metadata and the scraper runtime dependencies.
- Verified `python -m pip install -e .` installs the scraper into the active environment and makes `gaussian_scraper.search.search_docs` importable from the separate Inkly repository.
- Expanded the scraper README with virtual-environment, editable-install, verification, and Inkly shared-environment instructions.
- Recorded that the normal Inkly installation path should eventually provision/verify this dependency so end users do not have to remember separate manual setup commands.

Validation:
- Full scraper suite: 153 tests passed.
- `python -m pip check` reported no broken requirements.
- `git diff --check` and staged diff checks passed.
- Import verification succeeded both from the scraper repository and from the separate Inkly repository while using the shared `inkly-test` environment.

Scraper commit: `8b8cb4b1402c1486bc944360e028847ec395a225` (`Add scraper package installation setup`).
