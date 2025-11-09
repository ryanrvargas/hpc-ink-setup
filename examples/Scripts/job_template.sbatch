#!/bin/bash
##
## Generic single node CPU job template
## Adjust account, partition, time, memory, and CPUs as needed
##

#SBATCH --job-name=cpu-template
#SBATCH --account=your_account
#SBATCH --partition=compute
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

# Create log directory if missing
mkdir -p logs

echo "Job started on $(date)"
echo "Running on node(s): $SLURMD_NODENAME"
echo "CPUs per task: ${SLURM_CPUS_PER_TASK}"

# Load modules
module purge
module load gcc/12.2
module load python/3.10

# Optional environment
# export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}

# Work directory
cd "$SLURM_SUBMIT_DIR"

# Your command here
# Example: run a Python script that uses CPU threads
python scripts/run_cpu_work.py --threads "${SLURM_CPUS_PER_TASK}"

echo "Job finished on $(date)"
