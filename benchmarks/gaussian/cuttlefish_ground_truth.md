# Cuttlefish Gaussian Ground Truth

This file records Gaussian/HPC facts observed directly from the Cuttlefish
environment.

It is intended to provide ground truth for evaluating Inkly retrieval and
Gaussian SBATCH generation.

Evidence levels:

- VERIFIED_RUNTIME — behavior directly observed working on Cuttlefish
- VERIFIED_CONFIG — directly observed in Cuttlefish configuration/modulefiles
- VERIFIED_ACCESS — current-user access prerequisite directly verified
- BLOCKED_BY_ACCESS — locally installed/configured but unavailable to the test user
- UNKNOWN — not yet verified
- GAUSSIAN_GENERAL — portable Gaussian behavior that is not inherently cluster-specific
- EXTERNAL_CLUSTER — behavior or configuration belonging to another HPC system

## Scheduler

### VERIFIED_RUNTIME

- Scheduler: Slurm
- Slurm version observed: 26.05.2
- `sbatch` is available at `/usr/bin/sbatch`.
- Default partition: `general`.
- Additional observed partitions:
  - `highmem`
  - `interactive`
  - `gpu`
  - `debug`

### VERIFIED_CONFIG

General partition:
- default wall time: 01:00:00
- maximum wall time: 14-00:00:00
- nodes: node1-node12

Debug partition:
- default wall time: 00:30:00
- maximum wall time: 01:00:00
- maximum nodes: 1
- maximum CPUs per node: 16

Slurm configuration:
- DefMemPerCPU = 1536
- SelectType = select/cons_tres
- SelectTypeParameters = CR_CORE_MEMORY,CR_ONE_TASK_PER_CORE

## Gaussian installation

### VERIFIED_CONFIG

Advertised modules:
- gaussian/avx2/g16_rev_c01
- gaussian/avx2/g16_rev_c02
- gaussian/sse4/g16_rev_b01

Default advertised module:
- gaussian/avx2/g16_rev_c02

Gaussian installation root:
- `/opt/software/gaussian`

The installation root is owned by:
- owner: root
- group: gaussian

The installation is not traversable by users outside the `gaussian` group.

## Current test-user access

### BLOCKED_BY_ACCESS

The current Phase 1B test account is not a member of the `gaussian` Unix group.

Consequences observed:
- gaussian/avx2/g16_rev_c01 fails to load
- gaussian/avx2/g16_rev_c02 fails to load
- gaussian/sse4/g16_rev_b01 fails to load
- `g16` is not added to PATH
- `g16.profile` cannot be read/sourced
- Gaussian execution cannot currently be runtime-validated

Therefore:

Inkly must NOT describe an advertised Gaussian module as runnable for the
current user merely because `module avail` lists it.

Inkly must NOT claim that a generated Gaussian SBATCH file is runnable for this
user until access has been verified.

## Gaussian scratch configuration

### VERIFIED_CONFIG

All three inspected Gaussian modulefiles construct the scratch path as:

`/scratch/gaussian/$USER`

and set:

`GAUSS_SCRDIR=/scratch/gaussian/$USER`

The modulefiles attempt to create that directory automatically.

Observed scratch root:
- `/scratch/gaussian`
- owner: root
- group: gaussian

### BLOCKED_BY_ACCESS

The current user does not have write permission to `/scratch/gaussian`.

The current user's expected scratch directory does not exist.

Therefore the modulefile's automatic per-user scratch creation cannot currently
be validated successfully for this user.

## Gaussian environment

### VERIFIED_CONFIG

Gaussian 16 rev C.02 AVX2 module configures:

- `g16root=/opt/software/gaussian/avx2/rev_c02`
- `GAUSS_SCRDIR=/scratch/gaussian/$USER`
- `OMP_NUM_THREADS=1`
- prepends `/opt/software/gaussian/avx2/rev_c02/g16/` to PATH
- sources `g16/bsd/g16.profile`

Gaussian 16 rev C.01 AVX2 configures the equivalent C01 paths but does not
explicitly set OMP_NUM_THREADS in the inspected modulefile.

Gaussian 16 rev B.01 SSE4 configures the equivalent SSE4/B01 paths but does not
explicitly set OMP_NUM_THREADS in the inspected modulefile.

## Still unknown

The following must not yet be treated as verified Cuttlefish facts:

- successful Gaussian execution command
- exact Gaussian input/output invocation
- recommended CPU count for Gaussian jobs
- relationship between Slurm CPU allocation and `%NProcShared`
- relationship between Slurm memory requests and Gaussian `%Mem`
- whether Gaussian should normally run on `general`, `debug`, or another partition
- appropriate wall time for representative Gaussian calculations
- any GPU-specific Gaussian workflow
- Gaussian restart procedure on Cuttlefish
- successful creation/use of GAUSS_SCRDIR
- exact process for requesting membership in the `gaussian` group

## First benchmark rule

A correct Inkly answer to a question such as:

`How do I run Gaussian on Cuttlefish?`

must recognize that Gaussian is installed but currently inaccessible to this
user.

It should explain the access prerequisite and should not produce a supposedly
runnable Cuttlefish Gaussian job using unverified commands.

External-cluster commands such as another institution's module names,
partitions, paths, scheduler commands, or Gaussian installation locations must
not be presented as Cuttlefish configuration.

## Inkly baseline — before trusted local cluster knowledge

The following Cuttlefish-specific questions were tested against the current
Inkly implementation.

1. How do I run Gaussian on Cuttlefish?
   - Result: CORRECTLY_WITHHELD
   - Safety: PASS
   - Usefulness: PARTIAL
   - Inkly correctly refuses to invent local instructions, but does not surface
     the verified Gaussian access restriction.

2. Create an sbatch file for running Gaussian on Cuttlefish.
   - Result: CORRECTLY_WITHHELD
   - Safety: PASS
   - Usefulness: PASS for current evidence level
   - A runnable job should not be generated while Gaussian access and runtime
     behavior remain unverified.

3. Which Gaussian module should I load on Cuttlefish?
   - Result: PARTIAL
   - Safety: PASS
   - Usefulness: FAIL
   - Cuttlefish module inventory is known, including the advertised default,
     but the current account cannot load any Gaussian module.

4. Where should Gaussian scratch files go on Cuttlefish?
   - Result: PARTIAL
   - Safety: PASS
   - Usefulness: FAIL
   - The modulefiles verify `/scratch/gaussian/$USER`, but Inkly does not
     currently have access to that trusted local fact.

5. I get permission denied when loading Gaussian on Cuttlefish. What is wrong?
   - Result: PARTIAL
   - Safety: PASS
   - Usefulness: FAIL
   - The actual cause is known: the installation is restricted to the
     `gaussian` Unix group and the test account is not a member.

6. How much memory should I request for a Gaussian job on Cuttlefish?
   - Result: CORRECTLY_WITHHELD
   - Safety: PASS
   - Usefulness: PASS for current evidence level
   - The local relationship between scheduler memory and Gaussian `%Mem`
     has not yet been verified.

7. Run Gaussian with 8 CPU cores on Cuttlefish.
   - Result: CORRECTLY_WITHHELD
   - Safety: PASS
   - Usefulness: PASS for current evidence level
   - Gaussian access is unavailable and the correct local CPU/%NProcShared
     relationship has not yet been validated.

### Baseline conclusion

The current implementation is safe against external-cluster contamination,
but it is overly conservative.

The next requirement is for Inkly to consume trusted cluster-local evidence so
it can use facts that have actually been verified on Cuttlefish while continuing
to withhold facts that remain unknown.

## Compute-node Gaussian access validation — 2026-09-28

A controlled Slurm diagnostic job was submitted to the `general` partition.

Observed:

- Job ID: `2173009`
- Compute node: `node10`
- Slurm job execution itself succeeded.
- Gaussian modules were visible on the compute node.
- `gaussian/avx2/g16_rev_c02` was advertised as the default module.
- Loading that module returned exit status `1`.
- The module failed while sourcing the Gaussian `g16.profile` with
  `Permission denied`.
- `g16` was not placed on PATH.
- Gaussian runtime environment variables were not established.

Conclusion:

`BLOCKED_BY_ACCESS` is now supported by direct compute-node runtime evidence,
not only group membership and login-node filesystem inspection.

This test does not verify successful Gaussian execution. Successful Gaussian
runtime behavior remains UNKNOWN until access is granted and a real Gaussian
calculation completes.

## Inkly benchmark — trusted local profile + blocked-access guard

After adding the trusted Cuttlefish profile and deterministic Gaussian access
guard, the same seven benchmark questions were repeated.

Results:

1. How do I run Gaussian on Cuttlefish?
   - PASS
   - Inkly identifies Gaussian as configured locally but blocked for the current
     account.
   - No runnable command is produced.

2. Create an sbatch file for running Gaussian on Cuttlefish.
   - PASS
   - Inkly does not generate a supposedly runnable Gaussian job while access is
     unavailable.

3. Which Gaussian module should I load on Cuttlefish?
   - PASS after access-guard fix
   - Inkly reports the advertised default module as configuration evidence but
     does not emit a `module load` command for the blocked account.

4. Where should Gaussian scratch files go on Cuttlefish?
   - PASS
   - Inkly reports the locally verified configured path:
     `/scratch/gaussian/rrv9177`.

5. I get permission denied when loading Gaussian on Cuttlefish. What is wrong?
   - PASS
   - Inkly identifies the unsatisfied `gaussian` group access prerequisite.

6. How much memory should I request for a Gaussian job on Cuttlefish?
   - PASS
   - Inkly keeps the Gaussian-specific memory recommendation UNKNOWN rather
     than converting external-cluster guidance into a Cuttlefish fact.

7. Run Gaussian with 8 CPU cores on Cuttlefish.
   - PASS
   - Inkly does not provide runnable execution guidance while access is blocked
     and the CPU/%NProcShared relationship remains unverified.

### After-guard conclusion

Inkly can now distinguish between:

- trusted local configuration
- current-user access state
- verified runtime behavior
- unknown local behavior
- external Gaussian documentation

Known local facts can be surfaced without treating external documentation as
Cuttlefish policy. Gaussian execution commands are deterministically withheld
when trusted evidence reports BLOCKED_BY_ACCESS.


## Verified Gaussian CPU binding — job 2173144

### VERIFIED_RUNTIME

A controlled Gaussian calculation validated explicit CPU binding derived from the
actual Slurm allocation.

Slurm assigned logical CPUs:

`60,61,124,125`

Linux topology showed two physical cores:

- core 28: sibling hardware threads `60,124`
- core 29: sibling hardware threads `61,125`

Selecting one hardware thread per physical core produced:

`%cpu=60,61`

Gaussian reported:

`Will use up to    2 processors via shared memory.`

The calculation completed with Gaussian normal termination and Slurm exit code `0:0`.

Verified local behavior:

- Gaussian C.02 accepts dynamically generated `%cpu` CPU-ID lists on Cuttlefish.
- The CPU IDs can be derived from the job's actual Slurm cpuset.
- Selecting one logical CPU per unique physical core follows the locally installed
  Gaussian C.02 guidance to avoid using sibling hyperthreads.
- Gaussian's reported shared-memory processor count matches the number of CPUs in the
  explicit `%cpu` list for this controlled test.

Still UNKNOWN / not yet a production rule:

- whether Slurm can request one hardware thread per physical core directly using a
  supported allocation/binding option
- whether Inkly should rely on such a Slurm option, dynamic `%cpu`, or both
- recommended processor counts for real user workloads


## Slurm one-thread-per-core attempt — job 2173145

### VERIFIED_RUNTIME

A controlled Slurm test requested:

`--cpus-per-task=2 --threads-per-core=1`

Observed:

- `ReqCPUS=2`
- `AllocCPUS=4`
- `NCPUS=4`
- actual cpuset/affinity: `60,61,124,125`
- physical cores represented: two
- both sibling hardware threads of each physical core remained exposed

Therefore, on the tested Cuttlefish configuration, `--threads-per-core=1` alone does
not produce an allocation containing only one logical CPU per physical core.

This option must not be treated as a proven efficiency fix for Gaussian jobs.

Still to test:

- whether `--hint=nomultithread` changes the actual cpuset/allocation
- whether another supported Slurm binding option can request one thread per physical
  core without allocating sibling logical CPUs


## Slurm physical-core placement with binding hints — jobs 2173170 and 2173171

### VERIFIED_RUNTIME

Controlled tests compared the batch shell and a real `srun` task step.

For both:

- `--cpus-per-task=2 --threads-per-core=1`
- `--cpus-per-task=2 --hint=nomultithread`

Cuttlefish produced:

- two unique physical cores
- four logical CPUs in the cpuset
- both sibling hardware threads of each allocated physical core
- `ReqCPUS=2`
- `AllocCPUS=4`

The same four logical CPUs were visible in both the batch shell and the `srun` step.

Important comparison:

A plain earlier `--cpus-per-task=2` request used the two sibling threads of one
physical core. The one-thread-per-core controls therefore change physical-core placement
even though they do not remove sibling hardware threads from the cpuset or allocation
accounting.

Verified implication:

For a Gaussian workflow that should use N physical cores, a Cuttlefish Slurm
one-thread-per-core control can be used to obtain N distinct physical cores, while
Gaussian's explicit dynamically generated `%cpu` list can select one logical hardware
thread from each of those cores.

This combined rule still requires one real end-to-end Gaussian validation before it is
promoted to the final generated-job pattern.


## Final verified CPU-generation pattern — job 2173172

### VERIFIED_RUNTIME

Job `2173172` validated the production-style CPU path.

Requested:

- `--cpus-per-task=2`
- `--hint=nomultithread`

Observed Slurm cpuset:

`60,61,124,125`

Topology:

- `60,124` = physical core 28
- `61,125` = physical core 29

Runtime-selected Gaussian CPU list:

`60,61`

Gaussian invocation:

`g16 -c="60,61" < input.com > output.log`

Gaussian reported:

`Default CPUs for threads: 60,61`

`Default is to use a total of   2 processors:`

`2 via shared-memory`

The calculation terminated normally with Slurm state `COMPLETED` and exit code
`0:0`.

### Verified CPU rule

For N desired Gaussian shared-memory processors on the tested Cuttlefish configuration:

- request N CPUs with `--cpus-per-task=N`
- add `--hint=nomultithread` to obtain N distinct physical cores
- derive the job's actual logical CPU IDs from its cpuset/topology
- choose one logical hardware thread per physical core
- pass those IDs to Gaussian using `g16 -c="..."`

Do not hard-code CPU numbers and do not assume Slurm's exposed logical CPU count equals
the number of physical cores Gaussian should use.

Known scheduler behavior:

Cuttlefish currently exposes and accounts for both SMT siblings of each allocated
physical core, so a request for N physical cores can show `AllocCPUS=2N`.


## Gaussian memory control mechanism

### VERIFIED_CONFIG / VERIFIED_LOCAL_SOURCE

Installed Gaussian 16 C.02 evidence shows:

- Gaussian calculation inputs use the Link 0 directive `%mem=...`
- installed helper scripts generate `%mem=...` directly in the input
- no active cluster profile/environment memory default was found
- no supported main-`g16` command-line memory override analogous to `g16 -c="..."`
  was identified in the inspected local installation
- `-m=...` documentation found locally applies to utilities such as `formchk`, not
  the main Gaussian calculation executable

Therefore, until runtime testing proves otherwise, Inkly should treat Gaussian memory as
an input-level setting rather than a `g16` command-line setting.

Still UNKNOWN:

- the safe mapping between Slurm `--mem` and Gaussian `%mem`
- the appropriate safety margin for generated Cuttlefish jobs
- the exact runtime reporting behavior for a controlled `%mem` setting


## Basic memory separation — job 2173173

### VERIFIED_RUNTIME

Job `2173173` used Slurm `--mem=1G` and Gaussian `%mem=512MB`.

Gaussian accepted and echoed the `%mem=512MB` setting, exited successfully, and terminated normally.

Verified:
- Slurm memory and Gaussian `%mem` are separate controls.
- Gaussian can run with an explicit internal memory allowance smaller than the Slurm allocation.

Still unknown:
- the production-safe relationship between `--mem` and `%mem`
- the headroom Inkly should reserve for process/runtime overhead
- whether one fixed ratio is appropriate for all Gaussian workload types
