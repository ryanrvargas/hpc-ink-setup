# Cuttlefish Gaussian Access Test

Date: 2026-09-28

## Purpose

Determine whether the current user can load Gaussian inside a real Slurm
compute job, rather than relying only on login-node permissions or group
membership.

## Test

Submitted:

`benchmarks/gaussian/live_tests/gaussian_access_test.sbatch`

Slurm job:

- Job ID: 2173009
- Partition: general
- Compute node: node10
- Requested CPUs: 1
- Slurm state: COMPLETED
- Slurm exit code: 0:0

The diagnostic script intentionally exited with status 0 after collecting
evidence, so the Slurm COMPLETED state does not mean Gaussian itself loaded
successfully.

## Gaussian result

Inside the compute job:

- Gaussian modules were visible through Lmod.
- `gaussian/avx2/g16_rev_c02` was advertised as the default.
- `module load gaussian/avx2/g16_rev_c02` returned status 1.
- Loading failed while sourcing:
  `/opt/software/gaussian/avx2/rev_c02/g16/bsd/g16.profile`
- The failure was `Permission denied`.
- `g16` was not available on PATH after the failed module load.
- Gaussian environment variables were not established.

## Evidence classification

VERIFIED_RUNTIME:
- Slurm batch submission works for the current user.
- A job can execute on the Cuttlefish general partition.
- The diagnostic job successfully reached compute node node10.

VERIFIED_CONFIG:
- Gaussian modules are advertised on the compute node.
- `gaussian/avx2/g16_rev_c02` is the advertised default module.

BLOCKED_BY_ACCESS:
- The current user cannot load Gaussian on the login node.
- The current user also cannot load Gaussian inside a real compute job.
- The failure is caused by permission denial while accessing the Gaussian
  installation.

UNKNOWN:
- Successful Gaussian execution.
- Correct production Gaussian invocation.
- Slurm CPU to Gaussian `%NProcShared` mapping.
- Slurm memory to Gaussian `%Mem` mapping.
- Recommended Gaussian partition and wall time.
- A proven working production Gaussian SBATCH file.

## Conclusion

The Gaussian access restriction is not limited to the login node.

The same access failure occurs inside a real Slurm compute job. Inkly should
therefore treat Gaussian as installed and configured on Cuttlefish but not
currently runnable for this user.
