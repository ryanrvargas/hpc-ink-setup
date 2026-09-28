#!/bin/bash

#SBATCH --job-name=gaussian_access_test
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --output=gaussian_access_test-%j.out
#SBATCH --error=gaussian_access_test-%j.err

echo "===== JOB INFO ====="
echo "Host: $(hostname)"
echo "User: $(whoami)"
echo "Job ID: $SLURM_JOB_ID"
echo "CPUs: $SLURM_CPUS_PER_TASK"

echo
echo "===== USER GROUPS ====="
id

echo
echo "===== GAUSSIAN MODULES ====="
module avail gaussian 2>&1

echo
echo "===== LOAD GAUSSIAN ====="

module load gaussian/avx2/g16_rev_c02
LOAD_STATUS=$?

echo
echo "Gaussian module load status: $LOAD_STATUS"

echo
echo "===== MODULE LIST ====="
module list 2>&1

echo
echo "===== G16 PATH ====="
command -v g16 || echo "g16 NOT found on PATH"

echo
echo "===== GAUSSIAN ENVIRONMENT ====="
env | grep -E '^(g16root|GAUSS_SCRDIR|OMP_NUM_THREADS)=' || true

echo
echo "===== END TEST ====="

exit 0
