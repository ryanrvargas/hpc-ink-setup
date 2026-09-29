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

## 2026-09-14 — One-command Inkly setup

Completed the normal-user bootstrap path on `integration/gaussian-docs` so Inkly and the Gaussian documentation scraper can be provisioned through one setup command.

Changes:
- Added executable `setup.sh` as the user-facing setup entry point.
- Added `requirements.txt` with the Python 3.9/3.10 `tomli` compatibility dependency.
- `setup.sh` creates and reuses a private `~/.inkly/venv`, installs Inkly requirements, clones the scraper integration branch, installs the scraper into the private environment, runs Inkly's existing Python installer, and verifies `gaussian_scraper.search.search_docs` is importable.
- Updated `install.py` so the installed `ink` launcher uses the exact Python interpreter that ran the installer; normal users therefore do not need to activate Inkly's virtual environment before running `ink`.
- Added focused regression coverage for the installed launcher's interpreter and executable bit.
- Updated the README so normal users run `bash setup.sh`; `install.py` remains the internal installer.

Validation:
- Focused installer regression test: 1 passed.
- Full Inkly test suite: 96 passed.
- `bash -n setup.sh` passed.
- `git diff --check` and staged diff checks passed.
- A fresh end-to-end setup completed successfully under an isolated temporary home directory without touching the user's existing Inkly installation.
- The temporary install contained the private Python environment, scraper checkout, Inkly runtime, launcher, jobs database, and config.
- The installed launcher's shebang pointed to the temporary Inkly private Python interpreter.
- Re-running `setup.sh` against the same temporary installation completed successfully and reused the existing environment and scraper checkout.

Inkly commit: `db575774bd39eb3a8919e0041cdf23f2869f6b7a` (`Add one-command Inkly setup`).

## 2026-09-28 — Installed Ink validation and Alice Lab branch sync

Returned to the Cuttlefish Phase 1 Gaussian integration work on branch `integration/gaussian-docs`.

Initial validation:
- Working tree was clean.
- Full Inkly test suite passed: 115 tests.
- `python -m py_compile` passed.
- `git diff --check` passed.
- Ruff lint passed.
- Ruff formatting check passed.

Launcher/runtime investigation:
- The repository `./ink` launcher was newer than the installed `~/.inkly/bin/ink`.
- The installed runtime under `~/.inkly/lib/inkly` was also older than the current integration branch.
- This caused `ink` and `./ink` to behave differently.
- `./ink` correctly intercepted Cuttlefish-specific Gaussian questions and withheld unverified external cluster commands.
- The stale installed `ink` sometimes fell through to the model path, took roughly 27-34 seconds, and could return generic HPC instructions that were not verified for Cuttlefish.

Installed-runtime update:
- Created a backup of the existing Inkly installation before making changes.
- Ran the repository's existing `python install.py` installer instead of manually copying runtime files.
- The installer copied the current Inkly runtime into `~/.inkly/lib/inkly` and installed the current launcher into `~/.inkly/bin/ink`.
- Verified the installed launcher uses the intended Python interpreter.
- Verified the installed runtime contains the deterministic source-scoping logic.

Post-install Cuttlefish validation:
- `ink How do I run Gaussian on Cuttlefish?` returned the expected cluster-specific unavailable/not-verified response in about 0.077 seconds.
- `ink How do I submit a Gaussian job on Cuttlefish?` returned the same guarded response in about 0.072 seconds.
- The normal `ink` command now behaves like the validated source `./ink` path for these cluster-specific requests.

Repository synchronization:
- Confirmed Alice Lab `dev` is an ancestor of the Gaussian integration branch with no missing `dev` commits.
- Confirmed the organization repository contains `main`, `dev`, and `integration/gaussian-docs`.
- Did not bulk-copy old personal feature branches because many are historical and are not required for the current integration work.
- The personal `integration/gaussian-docs` branch contained one later documentation-only commit, `6bba0246` (`Record Phase 1 HPC validation and benchmark`).
- Fast-forwarded the local branch to that commit.
- Pushed the complete branch to `thealice-lab/hpc-ink-setup`.
- Local, personal GitHub, and Alice Lab copies of `integration/gaussian-docs` were synchronized at `6bba0246e46946c220b99bcccd75e0f6db6e15cf`.

Next:
- Commit and push this progress log.
- Merge `integration/gaussian-docs` into the Alice Lab `dev` branch through a pull request.
- Perform a fresh-install validation from updated `dev` to prove a normal user gets the correct `ink` command immediately after installation.

## 2026-09-28 — Fresh-install Gaussian source-scoping regression

Alice Lab PR #1 was merged into `dev` as merge commit `8c8ffe36b136ab180fe3f0d772d40d408a2bd55f`.

An isolated fresh-install validation was then performed using a temporary HOME so the existing user installation was not reused.

Fresh-install results:
- `setup.sh` completed successfully.
- The private Inkly Python environment was created.
- The Gaussian scraper package installed successfully.
- The installed `ink` launcher used the private Inkly Python interpreter.
- Running `ink` from outside the repository returned exactly `FINAL_OK` for the exact-output test.

A source-scoping regression was discovered during the clean-install Gaussian test.

Query:
`How do I run Gaussian on Cuttlefish?`

The fresh installation did not yet contain `~/.inkly/gaussian.db`. In this state, `docs_gaussian` returned a generic documentation-unavailable result rather than the cluster-specific unavailable marker expected by the runtime safety guard. The request therefore fell through to the LLM, which produced an unverified Cuttlefish-specific Gaussian command.

This is not acceptable behavior. Missing, corrupt, or empty documentation must never allow the model to invent local cluster commands.

Root cause:
- The runtime deterministic guard activates when `docs_gaussian` emits the cluster-unavailable marker.
- The plugin emitted that marker when external matches existed.
- Missing/corrupt databases and no-relevant-match paths returned generic messages without the marker.
- The LLM was therefore allowed to generate a cluster-specific answer.

A dedicated hotfix branch will make all cluster-specific Gaussian failure paths emit the deterministic unavailable marker and will add regression coverage for missing database, corrupt database, and no-relevant-match cases.

Personal PR #122 remains open and must not be closed until the hotfix is merged into Alice Lab `dev` and the clean-install test passes.


## 2026-09-28 — Fresh-install Gaussian source-scoping hotfix validated

Implemented the clean-install Gaussian source-scoping fix on branch
`fix/fresh-install-gaussian-source-scoping`.

Changes:
- Cluster-specific Gaussian queries now emit the deterministic unavailable marker when documentation retrieval is unavailable.
- Missing scraper/database, corrupt database, and no-relevant-match paths can no longer fall through to the LLM for local Gaussian commands.
- General Gaussian questions retain their existing behavior.
- Added regression coverage for all three clean-install/failure paths.

Validation:
- Targeted Gaussian/source-scoping tests: 16 passed.
- Full Inkly suite: 118 passed.
- `git diff --check` passed.
- Ruff lint passed.
- Ruff formatting check passed.

Fresh-install regression validation:
- Created a new isolated HOME.
- Ran the normal `setup.sh` installation from the hotfix branch.
- Confirmed no `~/.inkly/gaussian.db` existed in the clean installation.
- Ran the installed `ink` command from outside the repository.
- Exact-output test returned exactly `FINAL_OK`.
- `How do I run Gaussian on Cuttlefish?` returned the deterministic unavailable/not-verified response in about 0.06 seconds.
- `How do I submit a Gaussian job on Cuttlefish?` returned the same guarded response in about 0.05 seconds.
- No Gaussian module, executable, scheduler command, path, or other Cuttlefish-specific value was invented.

The clean-install regression is fixed and validated. Next step is to commit/push the hotfix, merge it into Alice Lab `dev`, then repeat the final installed-dev smoke test before closing personal PR #122 as superseded.

## 2026-09-28 — Added Gaussian operational validation gate

Reviewed the remaining Phase 1 work and identified a missing validation step.

Existing testing proves that:
- Gaussian documentation can be scraped and stored.
- Inkly can retrieve that documentation.
- External documentation is source-labeled and prevented from becoming unverified Cuttlefish facts.
- Retrieval and response paths function end-to-end.

However, these tests do not prove that the retrieved documentation is actually useful for creating correct Gaussian jobs on Cuttlefish.

Added a new Phase 1B operational-validation section before Phase 2.

Phase 1B will:
- collect known-good Gaussian job scripts that previously ran successfully on Cuttlefish
- identify the actual local SBATCH, Gaussian, resource, environment, scratch, and I/O requirements
- compare scraper-retrieved guidance against those known-good jobs
- distinguish verified Cuttlefish facts from useful external guidance and conflicting/outdated material
- test Inkly-generated Gaussian SBATCH files against known-good local examples
- add regression cases for verified local job patterns
- perform non-destructive scheduler/script validation where possible
- eventually run a minimal controlled Gaussian job if permitted
- create a repeatable Gaussian job-generation evaluation for future scraper/database changes

This operational validation is now considered part of Phase 1 completion before moving to Phase 2/MCP infrastructure work.


## 2026-09-28 — Final merged-dev fresh-install validation

Alice Lab PR #2 was merged into `dev` as
`d78c58759aa27fda0913e6e185a50c2c496a68ef`.

A final fresh-install validation was performed from that exact merged `dev`
commit using a new isolated HOME.

Results:
- `setup.sh` completed successfully.
- The Gaussian scraper dependency installed successfully.
- The installed `ink` launcher worked from outside the repository.
- The fresh installation intentionally had no `~/.inkly/gaussian.db`.
- Exact-output testing returned exactly `FINAL_OK`.
- `How do I run Gaussian on Cuttlefish?` returned the deterministic unavailable/not-verified response in about 0.06 seconds.
- `How do I submit a Gaussian job on Cuttlefish?` returned the same guarded response in about 0.06 seconds.
- No unverified Gaussian module, executable, scheduler command, partition, or path was generated.

The clean-install Gaussian source-scoping regression is therefore fixed and
validated on the authoritative Alice Lab `dev` branch.

The next Gaussian engineering stage is Phase 1B operational validation:
compare scraper retrieval and Inkly-generated Gaussian SBATCH files against
known-good jobs that actually ran successfully on Cuttlefish.


## 2026-09-28 — Personal repository synchronization complete

After final validation, the authoritative Alice Lab `dev` history was pushed to
the personal repository's `dev` branch.

Both repositories now point to the same validated `dev` commit:
`2a8f814`.

GitHub automatically recognized personal PR #122 as merged because its
integration history is now contained in personal `dev`. No separate manual
merge or close operation is required.

The Gaussian integration and fresh-install source-scoping work is now complete.
Before beginning Phase 1B, the operational-validation methodology will be
reviewed to determine the strongest way to measure whether scraper knowledge
actually improves useful and correct Gaussian SBATCH generation on Cuttlefish.


## 2026-09-28 — Phase 1B evaluation direction

Defined the broader operational goal for Inkly.

Inkly should reduce the amount of HPC/Linux-specific knowledge a user must
already know. A user should be able to describe the task they want to perform,
and Inkly should use verified information for the HPC system they are currently
using to provide correct guidance and, where appropriate, generate usable
Slurm SBATCH files.

Phase 1B will therefore evaluate the whole knowledge path rather than only
testing whether documentation retrieval technically works.

The evaluation will measure:
- whether the scraper contains information needed for realistic Gaussian/HPC tasks
- whether retrieval returns the right passages for those tasks
- whether local Cuttlefish facts are distinguished from general or external-cluster guidance
- whether Inkly can generate structurally and locally correct Gaussian SBATCH files
- whether controlled generated jobs can eventually execute successfully on Cuttlefish

Initial scraper review also identified an architectural limitation: retrieval
currently ranks passages primarily by textual relevance, while stored source
records do not yet provide a first-class classification for verified local
cluster information versus general Gaussian information or another cluster's
configuration.

Phase 1B will first establish ground truth and measure the current system before
deciding whether source-scope/provenance metadata or retrieval changes are
required.


## 2026-09-28 — Phase 1B initial Gaussian retrieval audit

Ran the first operational baseline against the current Gaussian documentation
database before changing retrieval, sources, or source-ranking behavior.

Current database:
- 3 sources
- 70 passages
- Harvard RC Gaussian documentation
- TACC Gaussian documentation
- NC State HPC Gaussian documentation

Ten realistic Gaussian/HPC queries were tested, covering:
- Slurm submission
- SBATCH generation
- CPU requests
- memory requests
- Gaussian %mem versus scheduler memory
- Gaussian %nprocshared versus scheduler CPUs
- scratch space
- input/output handling
- restarting calculations
- running Gaussian specifically on Cuttlefish

Key finding:
The current retrieval layer measures textual relevance but does not understand
operational compatibility or source authority.

For example, a query asking how to submit Gaussian using Slurm ranked an NC
State passage using `bsub` as its highest result. `bsub` is not a Slurm
submission command.

Other gaps were observed for:
- CPU allocation versus Gaussian %nprocshared
- scheduler memory versus Gaussian %mem
- scratch-space handling
- Gaussian restart workflows

A query explicitly asking how to run Gaussian on Cuttlefish still retrieved
only external-institution documentation.

Decision:
Do not optimize retrieval or add additional scraper sources blindly.

Phase 1B will first build a Cuttlefish Gaussian ground-truth validation set.
That ground truth will be used to measure source coverage, retrieval quality,
source correctness, generated SBATCH quality, and eventually real execution.

The working knowledge model will distinguish:
- VERIFIED_LOCAL: confirmed Cuttlefish-specific information
- GAUSSIAN_GENERAL: portable Gaussian behavior
- EXTERNAL_CLUSTER: another HPC system's commands/policies/examples
- COMMUNITY: tutorials, forums, and other lower-authority material

This classification is currently an evaluation concept. It will not be added
to the scraper schema until the ground-truth evaluation demonstrates what
metadata and retrieval behavior are actually required.


## 2026-09-28 — Live Cuttlefish Gaussian environment discovery

Phase 1B queried the live Cuttlefish environment rather than assuming that
external documentation or advertised modules represent working behavior.

Verified Cuttlefish scheduler facts:
- Slurm 26.05.2 is installed.
- `general` is the default partition.
- `general` has a 1-hour default time and a 14-day maximum time.
- Slurm reports a default memory value of `DefMemPerCPU=1536`.
- Additional visible partitions include highmem, interactive, gpu, and debug.

Verified Gaussian module inventory:
- gaussian/avx2/g16_rev_c01
- gaussian/avx2/g16_rev_c02 (default)
- gaussian/sse4/g16_rev_b01

An important operational failure was discovered:
loading the default `gaussian/avx2/g16_rev_c02` module currently fails while
Lmod attempts to source:

`/opt/software/gaussian/avx2/rev_c02/g16/bsd/g16.profile`

The shell reports `Permission denied`.

Because the module load fails:
- no Gaussian module remains loaded
- `g16` is not exposed through PATH
- Gaussian execution on this account is not yet verified

No historical Gaussian jobs were found in the current user's Slurm accounting
history or local job-script search.

Decision:
Do not create or submit a Gaussian benchmark job until the module-access issue
is understood. Phase 1B must distinguish "module advertised by the cluster"
from "module verified usable by the user." This is an example of the kind of
live cluster fact Inkly must eventually represent correctly.


## 2026-09-28 — Gaussian access root cause identified

The Gaussian module-loading failure was traced to filesystem/group access rather
than to one particular Gaussian module revision.

The current user is a member of the normal Cuttlefish HPC user groups but is
not a member of the Unix group `gaussian`.

The Gaussian installation root is owned by `root:gaussian` and is not
traversable by users outside that group. As a result, the current account
cannot access the Gaussian installation or source `g16.profile`.

All three advertised Gaussian modules were tested:
- gaussian/avx2/g16_rev_c01
- gaussian/avx2/g16_rev_c02
- gaussian/sse4/g16_rev_b01

All three failed with the same permission error.

This is therefore an account/access prerequisite, not a version-specific module
failure.

The readable C02 modulefile also provides configuration evidence including:
- g16root under /opt/software/gaussian/avx2/rev_c02
- per-user scratch under /scratch/gaussian/<user>
- OMP_NUM_THREADS=1
- Gaussian's executable directory added to PATH
- g16.profile sourced during module initialization

These values are treated as Cuttlefish configuration evidence but not yet as
successfully runtime-validated behavior because the current account cannot load
the software.

This discovery becomes an explicit Phase 1B benchmark case: Inkly should be
able to distinguish "software exists on the cluster" from "software is usable
by this user." When access is missing, it should explain the prerequisite
rather than generate a supposedly runnable job script.


## 2026-09-28 — Initial Cuttlefish Gaussian ground-truth set created

Created:

`benchmarks/gaussian/cuttlefish_ground_truth.md`

The benchmark separates directly observed Cuttlefish evidence into:
- VERIFIED_RUNTIME
- VERIFIED_CONFIG
- BLOCKED_BY_ACCESS
- UNKNOWN
- GAUSSIAN_GENERAL
- EXTERNAL_CLUSTER

This avoids treating all retrieved documentation as equally authoritative.

The initial record includes:
- Slurm and partition configuration
- advertised Gaussian modules
- Gaussian installation permissions
- current-user access failure
- configured Gaussian scratch behavior
- modulefile environment behavior
- explicitly unknown operational facts

This file will serve as the reference against which current Inkly behavior and
future scraper/retrieval changes are evaluated.


## 2026-09-28 — Inkly pre-local-knowledge baseline

Ran seven realistic Cuttlefish Gaussian questions against the current Inkly
implementation.

All seven queries returned the deterministic cluster-source withholding
response.

Conclusion:
The current implementation successfully prevents external documentation from
being rewritten as Cuttlefish fact, but it is now too conservative.

Inkly already has directly verified local facts available from Cuttlefish,
including:
- scheduler and partition information
- Gaussian module inventory
- Gaussian installation access restrictions
- configured Gaussian scratch location
- current-user group-access failure

The current Gaussian documentation path cannot expose those facts because
`docs_gaussian` intentionally treats its database as external documentation.

Architecture decision:
Do not mix trusted Cuttlefish facts into the external Gaussian scraper corpus.

Instead, add a generic trusted cluster-profile mechanism to Inkly. The local
profile will represent facts verified for the current HPC environment, while
Nathan's scraper remains responsible for broader Gaussian documentation and
external examples.

The eventual answer path should combine:
trusted local cluster evidence + relevant general documentation + user intent.

Verified facts may be answered directly. Unknown local facts must still be
withheld. External-cluster commands must remain explicitly scoped to their
source.

## 2026-09-28 — Gaussian compute-node access validation

Completed a controlled Slurm diagnostic to determine whether the previously
observed Gaussian access restriction was limited to the Cuttlefish login node.

Submitted job `2173009` to the `general` partition. The job ran on `node10`
and Slurm itself completed successfully.

Inside the compute job:

- Gaussian modules were visible.
- `gaussian/avx2/g16_rev_c02` was advertised as the default.
- The module load returned status 1.
- Lmod reported `Permission denied` while sourcing the Gaussian `g16.profile`.
- `g16` was not available on PATH after the failure.

This confirms that the current user's Gaussian access restriction also applies
inside a real compute job.

The diagnostic script deliberately exited 0 after collecting evidence, so the
Slurm COMPLETED state records successful execution of the diagnostic itself,
not successful execution of Gaussian.

Phase 1B now has direct evidence distinguishing:

- working Slurm batch execution
- installed/configured Gaussian software
- current-user Gaussian access failure
- still-unverified Gaussian runtime behavior

Next operational dependency:
obtain Gaussian access, then repeat validation with a minimal real Gaussian
calculation before treating generated Gaussian SBATCH files as proven runnable.

## 2026-09-28 — Trusted-profile benchmark after access guard

Repeated the seven-question Cuttlefish Gaussian benchmark after adding the
trusted local cluster profile and deterministic BLOCKED_BY_ACCESS guard.

The earlier unsafe module-answer behavior was corrected. Inkly no longer emits
a Gaussian `module load` command when trusted local evidence shows that the
current user lacks Gaussian access.

All seven benchmark cases now preserve the intended evidence boundaries:

- locally verified facts are surfaced
- blocked execution requests are stopped deterministically
- unknown Gaussian CPU and memory mappings remain unknown
- external documentation is not rewritten as Cuttlefish configuration

The implementation test suite currently passes 127 tests with Ruff and
formatting checks clean.


## 2026-09-29 — Gaussian access restored and real runtime validation

The `rrv9177` account is now a member of the Cuttlefish `gaussian` Unix group.

Fresh-session validation confirmed that `gaussian/avx2/g16_rev_c02` loads successfully,
`g16` is available on PATH, and the expected Gaussian environment and per-user scratch
directory are established.

Job `2173134` re-ran the same Slurm Gaussian-access skeleton that previously failed.
It completed `0:0` on `node7`, proving successful Gaussian module loading and `g16`
availability on a compute node after access was granted.

Job `2173135` verified compute-node Gaussian scratch behavior by creating and deleting
a probe file under `/scratch/gaussian/rrv9177`.

The installed Gaussian C.02 tests and helper scripts were inspected as local evidence.
Decision: use these files as evidence sources, but do not bulk-copy the proprietary
Gaussian test corpus into Inkly or Nathan's scraper database. Nathan's scraper remains
the broad external/general documentation layer; Cuttlefish runtime/configuration evidence
remains the trusted local layer.

A real Gaussian calculation was executed through Slurm using the installed
`test0000.com` water RHF/STO-3G case. Job `2173136` completed `0:0`; `g16`
returned 0, the SCF calculation completed, and Gaussian reported normal termination.
This runtime-verifies the basic Cuttlefish invocation pattern:

`g16 < input.com > output.log`

The vendor test's archive-specific options produced an archive warning but did not
prevent normal termination. Those test-specific options are not treated as production
recommendations.

### Reproducible CPU accounting issue

The Slurm CPU discrepancy is now reproducible rather than a one-off observation:

- Job `2173135`: `ReqCPUS=1`, `AllocCPUS=2`
- Job `2173136`: `ReqCPUS=1`, `AllocCPUS=2`
- Job `2173137`: `ReqCPUS=1`, `AllocCPUS=2`

Cuttlefish node topology shows two hardware threads per core, but the cause of the
accounting behavior is still `UNKNOWN`. Do not assume a mapping between Slurm
`--cpus-per-task` and Gaussian `%NProcShared` until controlled CPU-affinity,
core, and hardware-thread tests are completed.

Next investigation:
test controlled 1-, 2-, and 4-CPU Slurm allocations and inspect scheduler allocation,
CPU affinity, physical cores, and hardware threads before validating Gaussian
`%NProcShared`.


## 2026-09-29 — Cuttlefish CPU allocation probe

Ran controlled Slurm-only CPU allocation probes before changing Gaussian CPU guidance.

Jobs:

- `2173138`: requested `--cpus-per-task=1`
- `2173139`: requested `--cpus-per-task=2`
- `2173140`: requested `--cpus-per-task=4`

Observed:

### Job 2173138 — request 1

- `SLURM_CPUS_PER_TASK=1`
- `SLURM_CPUS_ON_NODE=2`
- Slurm: `ReqCPUS=1`, `AllocCPUS=2`
- affinity: logical CPUs `4,68`

### Job 2173139 — request 2

- `SLURM_CPUS_PER_TASK=2`
- `SLURM_CPUS_ON_NODE=2`
- Slurm: `ReqCPUS=2`, `AllocCPUS=2`
- affinity: logical CPUs `4,68`

### Job 2173140 — request 4

- `SLURM_CPUS_PER_TASK=4`
- `SLURM_CPUS_ON_NODE=4`
- Slurm: `ReqCPUS=4`, `AllocCPUS=4`
- affinity: logical CPUs `60,61,124,125`

The nodes report:

- 2 sockets
- 32 cores per socket
- 2 hardware threads per core
- 128 logical CPUs

Combined with the previously observed Cuttlefish Slurm configuration using core-based
allocation, the controlled affinity results strongly indicate that allocation is being
rounded at physical-core granularity and that Slurm is exposing both hardware threads
of the allocated core.

That interpretation is not yet promoted to a final verified fact. The next probe must
directly map affinity CPU IDs such as `4,68` and `60,61,124,125` to Linux
core/socket IDs and thread-sibling lists. Only after that direct topology check should
the physical-core explanation be marked verified.

Important limitation:

This scheduler behavior does NOT yet prove what value Gaussian `%NProcShared` should
use. The next validation must run controlled Gaussian calculations with explicit
`%NProcShared` values and inspect Gaussian's reported processor/thread usage against
the Slurm allocation and CPU affinity.

Do not generate CPU-aware Gaussian jobs from a guessed one-to-one relationship until
that runtime test is complete.


## 2026-09-29 — Direct CPU sibling topology verified

Ran direct Linux CPU topology probes for controlled Slurm allocations.

### Job 2173141 — requested 1 CPU

Observed:

- `SLURM_CPUS_PER_TASK=1`
- `SLURM_CPUS_ON_NODE=2`
- Slurm: `ReqCPUS=1`, `AllocCPUS=2`
- allowed CPUs: `4,68`
- CPU 4 -> core 4, socket 0, thread siblings `4,68`
- CPU 68 -> core 4, socket 0, thread siblings `4,68`

This directly proves that a one-CPU Slurm request is allocated one physical core and
both hardware threads of that core are exposed in the job's CPU affinity set.

### Job 2173142 — requested 2 CPUs

Observed:

- `SLURM_CPUS_PER_TASK=2`
- `SLURM_CPUS_ON_NODE=2`
- Slurm: `ReqCPUS=2`, `AllocCPUS=2`
- allowed CPUs: `4,68`
- both logical CPUs are the sibling threads of physical core 4 on socket 0

### Job 2173143 — requested 4 CPUs

Observed:

- `SLURM_CPUS_PER_TASK=4`
- `SLURM_CPUS_ON_NODE=4`
- Slurm: `ReqCPUS=4`, `AllocCPUS=4`
- allowed CPUs: `60,61,124,125`
- CPUs `60,124` are sibling threads of physical core 28 on socket 1
- CPUs `61,125` are sibling threads of physical core 29 on socket 1

### Verified scheduler conclusion

Cuttlefish's observed Slurm behavior is now supported by direct topology evidence:

- scheduler allocation occurs at physical-core granularity
- each physical core has two hardware threads
- both hardware threads of an allocated core are exposed in the job CPU affinity set
- a request for one CPU can therefore result in `AllocCPUS=2`
- a request for two CPUs can occupy the same one physical core
- a request for four CPUs spans two physical cores

This resolves the cause of the earlier repeatable `ReqCPUS=1 -> AllocCPUS=2` result.

Important limitation:

This does not yet define the correct Gaussian `%NProcShared` value. The next step is
to run controlled Gaussian calculations with explicit processor settings and compare
Gaussian's reported processor/thread behavior against the verified Slurm allocation.

End-of-day requirement:
before stopping the session, reconcile the Cuttlefish working branch with the personal
remote tracking commits and sync the completed Phase 1B branch to
`thealice-lab/hpc-ink-setup`.


## 2026-09-29 — Gaussian processor-source inspection

Inspected the installed Gaussian C.02 test inputs and logs before attempting to map
Slurm CPUs to Gaussian processor settings.

Findings:

- no explicit `%NProcShared` directives were found in the searched installed
  `tests/com/*.com` inputs
- multiple installed Gaussian test logs report:
  `Default is to use a total of   4 processors:`
- because the corresponding test inputs do not contain an explicit `%NProcShared`,
  the source of that four-processor default is not yet established
- it may come from Gaussian's test harness, command-line/runtime configuration, or
  another environment mechanism; this remains unverified until traced locally

Decision:

Do not use the test-log processor count as evidence that users should place
`%NProcShared=4` in Cuttlefish inputs.

Next:
trace the installed Gaussian scripts/environment for the source of the default processor
count, then run controlled Gaussian jobs with explicit processor settings only after the
local mechanism is understood.


## 2026-09-29 — Gaussian C.02 processor-control evidence

Inspected the locally installed Gaussian C.02 input examples, runtime environment,
helper scripts, profile, and release-note search results before defining how Inkly
should generate processor settings.

Observed:

- searched installed `tests/com/*.com` inputs contain no explicit
  `%NProcShared` directives
- Gaussian vendor reference logs frequently report a four-processor default, but
  those logs were generated in Gaussian's vendor/reference environment and do not
  establish a Cuttlefish runtime default
- the active Cuttlefish Gaussian environment exposes no `GAUSS_PDEF` or other
  processor-count environment variable
- the Cuttlefish module/profile sets `OMP_NUM_THREADS=1`
- the installed C.02 release notes state that `%nprocshared` and `%nproclinda`
  are deprecated and reference `%cpu` for processor/thread placement

Decision:

Do not make `%NProcShared` the default Inkly processor-control mechanism merely
because external HPC documentation uses it.

Before generating CPU-aware Gaussian jobs, inspect the locally installed C.02
release-note guidance for `%cpu` and processor affinity, then runtime-test that
mechanism against Cuttlefish's directly verified Slurm CPU affinity.

The vendor reference-log statement "Default is to use a total of 4 processors" is
not classified as a Cuttlefish local fact.


## 2026-09-29 — Gaussian C.02 local CPU guidance verified

Read the locally installed Gaussian 16 C.02 release notes rather than relying on
external HPC documentation for processor guidance.

The local Gaussian documentation states:

- `%cpu` specifies the specific CPUs used by Gaussian
- tying Gaussian threads to specific CPUs is the recommended mode of operation
- `%cpu` is preferred over processor-count-only control because it pins each thread
- `%nprocshared` and `%nproclinda` are deprecated
- hyperthreading is not useful for Gaussian
- when hyperthreading cannot be disabled, Gaussian jobs should use only one hardware
  thread from each physical CPU/core

This aligns directly with the Cuttlefish topology probes, which showed that Slurm
allocates physical cores while exposing both sibling hardware threads in the job
affinity set.

Important unresolved question:

The correct Inkly implementation is not yet known. A static `%cpu=0-N` line would
be unsafe because Slurm may assign different CPU IDs to each job. Before generating
a processor-aware Gaussian input, inspect successful real Cuttlefish Gaussian jobs
with no explicit `%cpu` directive to determine whether Gaussian automatically honors
the Slurm cpuset and how many threads it actually selects.

Only after observing that runtime behavior should Inkly either rely on Gaussian's
cpuset behavior or dynamically derive a `%cpu` directive from the Slurm allocation.


## 2026-09-29 — No implicit Gaussian CPU selection visible

Inspected the successful Gaussian runtime logs from jobs `2173136` and `2173137`
to determine what Gaussian selected when no explicit `%cpu` directive was present.

Both jobs:

- started Gaussian successfully
- completed normally
- contained no lines matching Gaussian's vendor-reference messages such as
  `Default CPUs for threads` or `Default is to use a total of ... processors`
- therefore do not provide direct evidence for the number or identity of processor
  threads Gaussian selected automatically

Conclusion:

Do not infer from successful execution that Gaussian automatically honored the desired
one-hardware-thread-per-physical-core policy.

The next controlled test will request a known Slurm allocation, read the actual Linux
cpuset and topology assigned to that job, select one logical CPU ID from each unique
physical core, construct an explicit Gaussian `%cpu` line from those runtime IDs, and
verify the calculation completes with that processor selection.

This avoids hard-coded CPU IDs and keeps the generated processor control grounded in the
actual Slurm allocation for each job.


## 2026-09-29 — Dynamic Gaussian %cpu runtime validation

Ran controlled Gaussian job `2173144` using a processor list derived from the
actual Slurm cpuset and Linux CPU topology at runtime.

Slurm allocation:

- requested `--cpus-per-task=4`
- `ReqCPUS=4`
- `AllocCPUS=4`
- node: `node7`
- job affinity: `60,61,124,125`

Direct topology mapping showed:

- CPUs `60,124` are sibling hardware threads of physical core 28
- CPUs `61,125` are sibling hardware threads of physical core 29

The job selected one logical CPU from each physical core:

`60,61`

and generated the Gaussian Link 0 directive:

`%cpu=60,61`

Gaussian runtime then reported:

`Will use up to    2 processors via shared memory.`

The calculation:

- returned `g16` exit status 0
- completed the RHF/STO-3G water calculation
- reported normal Gaussian termination
- completed in Slurm state `COMPLETED` with exit code `0:0`

Conclusion:

The dynamic processor-selection mechanism is now `VERIFIED_RUNTIME` for this
controlled Cuttlefish workflow:

1. obtain the CPUs assigned by Slurm
2. map assigned logical CPUs to physical socket/core IDs
3. select one logical CPU from each unique physical core
4. generate a Gaussian `%cpu=<actual assigned CPU IDs>` directive
5. Gaussian honors the explicit list and reports the corresponding shared-memory
   processor count

Important remaining design question:

The tested job requested four Slurm CPUs in order to receive two physical cores because
the current Cuttlefish allocation exposes two hardware threads per core. Before making
this Inkly's final resource-generation rule, test whether supported Slurm options can
request one hardware thread per physical core directly. If so, that may avoid requesting
unused sibling hardware threads. The dynamic `%cpu` mechanism remains a proven fallback.


## 2026-09-29 — Slurm threads-per-core test

Tested whether Cuttlefish can avoid allocating unused sibling hardware threads by
submitting a two-CPU job with:

`--cpus-per-task=2 --threads-per-core=1`

Job `2173145` completed successfully on `node7`.

Observed:

- `ReqCPUS=2`
- `AllocCPUS=4`
- `NCPUS=4`
- `SLURM_CPUS_PER_TASK=2`
- `SLURM_CPUS_ON_NODE=2`
- actual Linux affinity: `60,61,124,125`

Topology:

- `60,124` are sibling hardware threads of physical core 28
- `61,125` are sibling hardware threads of physical core 29

Conclusion:

On the current Cuttlefish Slurm configuration, `--threads-per-core=1` by itself does
not reduce the actual allocated logical CPU set to one hardware thread per physical
core. The accounting allocation still includes both sibling threads of each allocated
physical core.

Do not generate this option in Inkly as an efficiency optimization unless another
supported Slurm binding/hint combination is runtime-verified to change the actual
allocation/cpuset.

Next:
test `--hint=nomultithread` if supported. If Cuttlefish still allocates/exposes sibling
threads, retain dynamic Gaussian `%cpu` selection as the verified mechanism and treat
the extra sibling allocation as a scheduler-level characteristic rather than something
Inkly can safely remove with a simple SBATCH directive.


## 2026-09-29 — Cuttlefish checkout reconciled after reconnect

After reconnecting to Cuttlefish, verified and safely reconciled the active Phase 1B
working copy.

State after reconciliation:

- active branch: `phase1b/gaussian-operational-validation`
- local Cuttlefish HEAD: `177ce37`
- personal GitHub Phase 1B HEAD: `177ce37`
- Alice Lab Phase 1B HEAD: `01c9823`
- local versus personal remote: synchronized
- Alice Lab remains behind and is still scheduled for end-of-day synchronization

Before fast-forwarding, the three locally modified tracking documents were backed up
under:

`~/inkly-phase1b-presync-20260929`

The working copy was then fast-forwarded from `01c9823` to `177ce37`.

All untracked live-validation artifacts from Gaussian and Slurm jobs through job
`2173145` remained intact. No live-test output or scripts were deleted or reset.

Next:
resume the Slurm binding experiment to compare `--threads-per-core=1`,
`--hint=nomultithread`, and actual `srun` task affinity before finalizing Inkly's
Gaussian CPU-generation rule.


## 2026-09-29 — Slurm binding and srun affinity comparison

Ran controlled Slurm binding probes with an actual `srun` step to distinguish
scheduler allocation, batch-shell affinity, and task-step affinity.

### Job 2173170 — `--cpus-per-task=2 --threads-per-core=1`

Observed:

- `ReqCPUS=2`
- `AllocCPUS=4`
- batch-shell affinity: `60,61,124,125`
- `srun` step affinity: `60,61,124,125`
- logical CPUs exposed: 4
- unique physical cores represented: 2
- `60,124` are sibling threads of one physical core
- `61,125` are sibling threads of another physical core

### Job 2173171 — `--cpus-per-task=2 --hint=nomultithread`

Observed the same topology and accounting behavior:

- `ReqCPUS=2`
- `AllocCPUS=4`
- batch-shell affinity: `60,61,124,125`
- `srun` step affinity: `60,61,124,125`
- logical CPUs exposed: 4
- unique physical cores represented: 2

### Important comparison with the earlier plain two-CPU request

Earlier job `2173139`, submitted with only `--cpus-per-task=2`, was confined to
logical CPUs `4,68`, which are sibling hardware threads of a single physical core.

Therefore the one-thread-per-core Slurm controls do have a useful effect on Cuttlefish:
they cause a two-CPU request to span two distinct physical cores rather than two sibling
threads of one core.

However, they do not reduce the actual cpuset or Slurm allocation accounting to one
logical CPU per physical core. Both sibling hardware threads remain visible and
`AllocCPUS` is 4.

Current best-supported CPU strategy:

1. request N CPUs with a verified one-thread-per-core Slurm control
2. Slurm places those N requested CPUs across N physical cores
3. inspect the actual job cpuset/topology
4. select one logical CPU from each unique physical core
5. generate Gaussian `%cpu=<selected CPU IDs>`
6. Gaussian uses exactly those pinned processors

This should be validated end-to-end with a real Gaussian job before becoming Inkly's
final CPU-generation rule.


## 2026-09-29 — Production-style Gaussian CPU path verified

Ran end-to-end Gaussian job `2173172` using the proposed Phase 1B CPU-generation
pattern.

SBATCH resources:

- `--cpus-per-task=2`
- `--hint=nomultithread`
- `--mem=1G`

Cuttlefish/Slurm behavior:

- `ReqCPUS=2`
- `AllocCPUS=4`
- job cpuset: `60,61,124,125`
- physical core 28: sibling threads `60,124`
- physical core 29: sibling threads `61,125`

The runtime wrapper selected one logical CPU from each unique physical core:

`60,61`

Instead of rewriting the Gaussian input file, the job passed the dynamically selected
CPU list through Gaussian's locally documented command-line processor option:

`g16 -c="60,61" < input.com > output.log`

Gaussian explicitly reported:

- `Default CPUs for threads: 60,61`
- `Default is to use a total of   2 processors:`
- `2 via shared-memory`

The calculation exited with status 0 and reported normal Gaussian 16 termination.

### Phase 1B CPU rule — VERIFIED_RUNTIME

For a Cuttlefish Gaussian job requesting N shared-memory processors:

1. request `--cpus-per-task=N`
2. include `--hint=nomultithread` so the request is placed across N distinct
   physical cores
3. inspect the actual job cpuset and Linux socket/core topology at runtime
4. select one logical CPU from each unique physical core
5. require exactly N selected physical cores
6. invoke Gaussian with `g16 -c="<actual selected CPU IDs>"`

This preserves the user's Gaussian input file and pins Gaussian threads to the actual
CPUs allocated to the job.

Cuttlefish still exposes/accounts for both SMT siblings, so `AllocCPUS` may be 2N.
That is a scheduler-level characteristic observed on this cluster, not something Inkly
should hide or claim to eliminate.


## 2026-09-29 — Gaussian memory evidence inspection

Inspected the locally installed Gaussian 16 C.02 release notes, active module
environment/profile, and installed test inputs before defining Inkly's memory rule.

Observed:

- the active Cuttlefish Gaussian profile contains no explicit memory setting found by
  the memory search
- the active Gaussian environment exposes no `GAUSS_MDEF` or other memory-default
  variable found by the memory search
- installed Gaussian test inputs use `%mem` directly
- installed examples include units such as `gb`, `mb`, and `mw`, plus raw numeric
  forms
- the local C.02 performance notes recommend larger memory allocations for larger
  calculations and discuss memory scaling with processor count

Important distinction:

The installed Gaussian performance guidance is not automatically a Cuttlefish
scheduler rule. No mapping such as `Gaussian %Mem = Slurm --mem` or a fixed percentage
of Slurm memory has been runtime-verified yet.

Next:

1. trace the installed Gaussian memory default/override mechanism, including any
   supported command-line or environment equivalent to `%mem`
2. run a controlled Gaussian job under a known Slurm memory allocation
3. inspect Gaussian's own runtime memory reporting
4. only then select an Inkly memory-generation rule


## 2026-09-29 — Future direction: reusable HPC onboarding

Agreed that the Cuttlefish validation work should become the reference implementation
for a reusable Inkly cluster onboarding and validation system.

Goal:

Do not require the same manual investigation for every new HPC. Instead, after the
current Cuttlefish Phase 1B work is complete, design a safe setup flow that can inspect
and validate a new cluster, build a trusted local profile, and let Inkly become
cluster-specific without hard-coding one institution.

Target architecture:

general HPC/application knowledge
+ verified cluster profile
+ runtime validation evidence
+ user request
-> cluster-specific Inkly guidance / generated job

The future onboarding flow should be able to discover and/or validate items such as:

- cluster identity / hostname
- scheduler and partitions
- CPU topology and binding behavior
- memory behavior
- scratch paths and permissions
- installed modules/software
- application access
- small safe runtime validation jobs

The resulting profile should contain only verified local facts and retain evidence
classification such as VERIFIED_RUNTIME, VERIFIED_CONFIG, VERIFIED_ACCESS,
VERIFIED_LOCAL_SOURCE, DOCUMENTED_ONLY, EXTERNAL, and UNKNOWN.

A possible future UX is an `ink init` or `ink init-cluster` workflow that safely
builds the local cluster profile and ground truth before Inkly begins generating
cluster-specific commands.

Cuttlefish is the first reference implementation for this framework, not a set of
special cases that should be embedded permanently into Inkly core.


## 2026-09-29 — Gaussian memory control path

Inspected the installed Gaussian 16 C.02 executable, scripts, release notes, profile,
and utility examples to determine whether Gaussian memory can be controlled externally
the way CPU binding can be controlled with `g16 -c="..."`.

Observed:

- `g16` is a direct ELF executable, not a shell wrapper
- no `GAUSS_MDEF` or equivalent main-Gaussian memory environment default was found
- no installed `g16` command-line memory option equivalent to `-c` was identified
- installed helper scripts such as `mygau` generate a `%mem=...` line in the
  Gaussian input
- the `-m=1gb` command-line example in the release notes applies to the `formchk`
  utility, not to the main `g16` calculation executable
- no Default.Route file was found in the searched installed tree

Current design implication:

Keep CPU placement external through `g16 -c="..."`, but treat Gaussian calculation
memory as an input-level Link 0 setting using `%mem=...` unless later runtime evidence
shows a supported alternative.

Next:
run a controlled Gaussian calculation with a known Slurm `--mem` allocation and an
explicit `%mem` value, then inspect Gaussian's own runtime memory reporting before
choosing any mapping formula.


## 2026-09-29 — Basic memory separation runtime check

Job `2173173` validated the basic relationship between scheduler memory and Gaussian memory settings.

Observed:
- Slurm requested `--mem=1G`
- Slurm reported `ReqMem=1G`
- Gaussian input used `%mem=512MB`
- Gaussian echoed `%mem=512MB`
- `g16` exited 0
- Gaussian terminated normally

Conclusion:
Slurm memory and Gaussian `%mem` are separate controls. This test proves that Gaussian can run with an internal memory allowance smaller than the Slurm allocation.

It does not establish a production ratio. The small water calculation did not pressure memory enough to justify a fixed percentage.

Next:
determine a safe Inkly mapping between Slurm `--mem` and Gaussian `%mem`, then validate that mapping with a more memory-demanding local test.


## 2026-09-29 — Gaussian memory accounting probe 2173174

Job `2173174` tested Gaussian `%mem=768MB` inside a Slurm `--mem=1G` allocation.

Observed:

- `SLURM_MEM_PER_NODE=1024`
- `SLURM_MEM_PER_CPU` unset
- Gaussian accepted `%mem=768MB`
- `g16` exit status 0
- Gaussian normal termination
- GNU time maximum resident set size: approximately 291840 KB
- task-level cgroup `memory.max` reported `max`

Interpretation:

The job was too small to pressure the requested 768 MB Gaussian memory allowance, so
it does not establish a safe production ratio between Slurm memory and Gaussian memory.

The task-level `memory.max=max` result also does not prove that Slurm's 1 GB limit is
unenforced; the effective memory limit may be attached to a parent Slurm cgroup. Inspect
the cgroup hierarchy before drawing a scheduler enforcement conclusion.


## 2026-09-29 — Slurm memory enforcement verified

Job `2173175` inspected the Cuttlefish cgroup v2 hierarchy for a job submitted with
`--mem=1G`.

Observed:

- `SLURM_MEM_PER_NODE=1024`
- Slurm `ReqMem=1G`
- Slurm `AllocTRES` included `mem=1G`
- the task-level cgroup had `memory.max=max`
- the parent Slurm user/job cgroup had:
  - `memory.max=1073741824`
  - `memory.high=1073741824`
- the Slurm job root also had the same 1073741824-byte limits
- cgroup v2 is active
- `ProctrackType=proctrack/cgroup`
- `TaskPlugin=task/cgroup`
- `ConstrainRAMSpace=yes`
- `AllowedRAMSpace=100`

Conclusion:

Cuttlefish does enforce the requested Slurm memory allocation through cgroup v2.
A `--mem=1G` request creates an effective one-GiB memory boundary for the job.

Therefore Inkly must ensure Gaussian's internal `%mem` setting plus Gaussian/runtime
overhead remain below the Slurm allocation. Giving Gaussian the full Slurm memory
allocation is not automatically safe.

Next:
identify a local Gaussian workload that actually consumes a substantial fraction of its
configured `%mem` so the necessary headroom can be measured rather than guessed.


## 2026-09-29 — Memory stress candidate scan

Scanned installed Gaussian reference tests for inputs with explicit `%mem` settings and
short reference runtimes.

Leading candidate: `test0977`

- input uses `%mem=2gb`
- reference CPU time is approximately 31.8 seconds
- Gaussian reference output reports `MaxMem=268435456`

Important interpretation:
Gaussian's `MaxMem` value is the program's internal configured memory ceiling
(expressed in Gaussian's internal word units), not Linux peak resident memory.
For `test0977`, 268435456 8-byte words corresponds to 2 GiB, matching `%mem=2gb`.

Therefore the reference log confirms the configured Gaussian limit but does not tell us
the actual RSS. A live Slurm run with GNU time / cgroup accounting is still required.

Before running the vendor test, inspect `test0977` for external files, checkpoints,
multi-step dependencies, or other assumptions so the validation remains safe and
self-contained.


## 2026-09-29 — Selected live Gaussian memory candidate

Inspected installed Gaussian test `test0977`.

The input is self-contained:

- one Link 0 directive: `%mem=2gb`
- one route section
- no `%oldchk`, checkpoint-read, external-file, or multi-Link1 dependency found
- reference output contains one normal termination
- reference CPU and elapsed time are approximately 31.8 seconds
- reference scratch/file sizes are modest

The reference `MaxMem` value matches the configured Gaussian memory ceiling but is not
a Linux RSS measurement.

Decision:
use `test0977` for the live Cuttlefish memory measurement, with a Slurm allocation
larger than 2 GiB so the first run measures real peak use rather than intentionally
testing the OOM boundary.


## 2026-09-29 — test0977 live memory measurement

Ran installed Gaussian test `test0977` as job `2173176` with:

- `--cpus-per-task=3`
- `--hint=nomultithread`
- Slurm `--mem=4G`
- Gaussian input `%mem=2gb`

Runtime CPU selection chose `60,61,62` across three physical cores.

Observed:

- Gaussian exited 0 and terminated normally
- Gaussian reported three processors
- Slurm cgroup limit: 4294967296 bytes (4 GiB)
- GNU time maximum RSS: 318244 KB
- cgroup `memory.peak`: 332816384 bytes (~317.4 MiB)
- Gaussian `MaxMem` reflected the configured 2 GiB ceiling

Conclusion:

`test0977` does not actually consume memory close to its configured `%mem=2gb`.
The configured Gaussian memory ceiling must not be treated as expected RSS.

Therefore this workload cannot justify a production Slurm/Gaussian memory headroom
ratio. Select a workload whose measured RSS materially approaches its configured
Gaussian memory allowance before defining Inkly's memory rule.


## 2026-09-29 — Memory candidate ranking after test0977

Ranked installed Gaussian reference tests by the largest observed `NReq` relative to
their configured `MaxMem`, while preferring runs with practical reference runtimes.

Useful candidates included:

- `test0875`: ratio ~0.624, ~259 s CPU time
- `test0983`: ratio ~0.602, ~58.4 s CPU time
- `test0400`: ratio ~0.597, ~116.6 s CPU time
- `test0934`: ratio ~0.595, but reference CPU time reported 0.0 s and input includes a rearchive step

Decision:
inspect `test0983` next because it combines a high memory-demand indicator with a much
shorter reference runtime. The NReq/MaxMem ratio is only a screening heuristic; actual
Linux RSS/cgroup peak still must be measured on Cuttlefish.


## 2026-09-29 — test0983 dependency inspection

Inspected installed Gaussian test `test0983`.

Findings:

- input uses `%mem=100mw` for each section
- it contains eight `--Link1--` calculations
- relative checkpoint files `test0983a`, `test0983b`, `test0983c`, and
  `test0983d` are created/reused within the same multi-link input
- no pre-existing external checkpoint or input dependency is required
- reference output contains eight normal terminations
- several reference links report `NReq` around 63 million words against
  `MaxMem=104857600` words, giving an NReq/MaxMem screening ratio near 0.60

Decision:
run the installed input directly from its read-only Gaussian installation path, but use
an isolated per-job working directory so its relative checkpoint files cannot collide
with other runs. Measure actual Linux RSS and cgroup peak; do not treat NReq as actual
resident memory.


## 2026-09-29 — test0983 live memory measurement

Ran installed Gaussian test `test0983` as Slurm job `2173177` in an isolated
per-job working directory.

Resources:

- `--cpus-per-task=4`
- `--hint=nomultithread`
- `--mem=2G`
- Gaussian `%mem=100mw` for each Link1 section

Runtime:

- selected physical-core CPU IDs: `29,30,31,60`
- all eight Gaussian sections terminated normally
- Slurm cgroup limit: 2147483648 bytes (2 GiB)
- aggregate cgroup memory peak: 927997952 bytes (~885 MiB)
- GNU time maximum RSS: 621892 KB (~607 MiB)
- Gaussian internal `MaxMem=104857600` words, corresponding to the configured
  `%mem=100mw` (~800 MiB using 8-byte words)
- largest observed `NReq` remained around 63 million words

Interpretation:

This is the first live test where aggregate job memory materially approaches and
slightly exceeds Gaussian's configured internal memory allowance. The cgroup peak was
approximately 1.106 times the configured Gaussian memory ceiling, or about 85 MiB above
800 MiB.

The cgroup peak is more relevant than GNU time MaxRSS for scheduler sizing because the
Gaussian driver launches child Link executables and the cgroup measures aggregate job
memory.

Do not promote 10.6% to a universal overhead constant from one workload. Use it as
evidence that `%mem` must remain below Slurm `--mem`, and validate a conservative
production margin with another controlled run.


## 2026-09-29 — test0983 tight 1 GiB validation

Repeated installed Gaussian `test0983` as job `2173178` with the same Gaussian
memory setting but a tighter Slurm memory boundary.

Configuration:

- Slurm `--mem=1G`
- effective cgroup limit: 1073741824 bytes
- Gaussian `%mem=100mw` (~800 MiB)
- nominal Gaussian/Slurm ratio: 0.78125
- nominal headroom: 224 MiB
- four explicitly selected physical-core CPU IDs

Observed:

- all eight Gaussian Link1 calculations terminated normally
- job completed with exit code 0
- GNU time MaxRSS: 617328 KB
- cgroup memory peak: 752685056 bytes (~717.8 MiB)
- remaining cgroup margin at measured peak: ~306 MiB

Comparison with job 2173177:

- GNU MaxRSS was very similar between the 2 GiB and 1 GiB Slurm runs
- cgroup peak was lower in the tighter-memory run

Interpretation:

The similar process MaxRSS suggests the Gaussian workload itself behaved consistently.
The differing cgroup peaks indicate that cgroup peak can include memory behavior beyond
the main process RSS, including reclaim/cache effects, so a single cgroup peak should
not be converted directly into a universal overhead percentage.

Verified for this workload:
Gaussian `%mem=100mw` (~800 MiB) runs successfully inside a Cuttlefish Slurm
`--mem=1G` allocation.

Before defining Inkly's Phase 1B memory rule, repeat the same candidate ratio on a
different Gaussian workload class.


## 2026-09-29 — test0400 selected for cross-workload memory validation

Inspected installed Gaussian test `test0400` as a second workload class for memory
validation.

Findings:

- two self-contained Link1 sections
- both use `%mem=100mw`
- no checkpoint, old-checkpoint, external-file, or geometry/guess-read dependency
- workload is open-shell TD-DFT, unlike the GHF/DFT multi-link `test0983`
- reference output contains two normal terminations
- largest observed `NReq=62618576` words
- `MaxMem=104857600` words
- screening ratio is about 0.597
- reference elapsed time is about 30 seconds per section

Decision:
run `test0400` under the same tested memory relationship used for the successful
`test0983` tight-memory run: Slurm `--mem=1G` with Gaussian `%mem=100mw`.
This provides a cross-workload check before defining Inkly's Phase 1B memory policy.


## 2026-09-29 — cross-workload memory validation complete

Ran installed Gaussian TD-DFT test `test0400` as job `2173179`.

Configuration:

- Slurm `--mem=1G`
- effective cgroup limit: 1073741824 bytes
- Gaussian `%mem=100mw` (~800 MiB)
- four explicitly bound physical-core CPUs
- two Link1 calculations

Observed:

- job completed with exit code 0
- both Gaussian sections terminated normally
- GNU time MaxRSS: 532164 KB
- aggregate cgroup peak: 673034240 bytes (~641.9 MiB)
- measured remaining cgroup margin: ~382.1 MiB
- largest observed `NReq=62618576` words

This independently confirms the same tested memory relationship previously validated
with `test0983`: Gaussian `%mem=100mw` (~800 MiB) operates successfully inside an
enforced 1 GiB Cuttlefish Slurm memory allocation.

Phase 1B memory policy evidence now covers two materially different Gaussian workload
classes (GHF/DFT multi-link and TD-DFT).

Recommended Phase 1B generation policy:
- keep Gaussian `%mem` below Slurm `--mem`
- for automatically generated Cuttlefish jobs, use a conservative maximum Gaussian
  internal memory target of about 75-78% of the requested Slurm job memory
- round downward to a simple Gaussian memory value
- never set `%mem` equal to the Slurm memory limit
- preserve explicit user-provided Gaussian memory only if it fits below the scheduler
  allocation with the configured safety margin; otherwise warn/adjust
- retain the policy as conservative cluster guidance rather than a universal Gaussian
  law

Memory validation experiments can stop here for Phase 1B; next work is implementation
and regression coverage.


## 2026-09-29 — Phase 1B memory policy implementation prepared

Prepared the trusted-profile implementation for the verified Cuttlefish Gaussian runtime
policy.

Changes prepared on `phase1b/gaussian-operational-validation`:

- mark Cuttlefish Gaussian runtime as verified
- record the verified `general` Slurm partition
- record the physical-core CPU selection and `g16 -c=<selected_cpu_ids>` launch rule
- record that Slurm `--mem` is cgroup-enforced
- record a conservative automatic Gaussian memory cap of 75% of Slurm memory, rounded
  downward
- record the 1 GiB Slurm / ~800 MiB Gaussian validations from `test0983` and
  `test0400`
- expose those rules through the trusted cluster-profile plugin
- add plugin regression assertions
- strengthen the generic runtime contract to prefer verified local generation rules over
  external-cluster guidance

These changes are prepared but not yet marked complete. They must pass targeted tests,
the full pytest suite, Ruff, format checks, and a real Cuttlefish plugin-output check.


## 2026-09-29 — Phase 1B implementation validation

Validated the prepared Cuttlefish Gaussian runtime policy on the actual cluster.

Results:

- targeted cluster-profile/runtime tests: 9 passed
- full pytest suite: 127 passed
- Ruff lint: passed
- live trusted-profile output correctly reported:
  - Gaussian runtime verified
  - verified Slurm partition `general`
  - `--cpus-per-task=N` and `--hint=nomultithread`
  - dynamic one-thread-per-physical-core selection
  - `g16 -c=<selected_cpu_ids>`
  - Slurm `--mem` cgroup enforcement
  - automatic Gaussian memory rule capped at 75% of Slurm memory and rounded down
  - successful local validation from `test0983` and `test0400`

The only tracked-code validation issue was Ruff format on
`inkly/plugins/cluster_profile.py`; a formatting-only fix was applied remotely.

The full repository format check also reports the untracked live-test helper
`benchmarks/gaussian/live_tests/cpu_affinity_report.py`. That file is a local
validation artifact and should remain separate from production changes unless we
explicitly decide to keep it.


## 2026-09-29 — Phase 1B trusted-profile implementation validated

Final Cuttlefish validation after the formatting fix succeeded:

- targeted trusted-profile/runtime tests: 9 passed
- full test suite: 127 passed
- Ruff lint: passed
- Ruff format check: all 69 checked files formatted
- `git diff --check`: passed
- live profile assertion: `TRUSTED_PROFILE_VALIDATION_OK`

The live trusted profile exposes the verified Cuttlefish Gaussian facts required for
generation: runtime status, `general` partition, CPU request/binding rule, cgroup
memory enforcement, and the conservative 75% automatic Gaussian memory cap.

The Phase 1B trusted-profile/memory implementation is complete.

Next:
exercise Inkly itself with a user-facing Cuttlefish Gaussian/SBATCH request and verify
that the resulting answer actually follows the trusted rules. Any failure at that layer
should be fixed with regression coverage rather than changing the already-verified
cluster ground truth.

The numerous files under `benchmarks/gaussian/live_tests/` remain untracked local
validation artifacts and were not added to the production implementation.
