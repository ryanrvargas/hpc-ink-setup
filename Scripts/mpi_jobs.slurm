#!/bin/bash
##
## Multi node MPI job example using srun
## Adjust nodes, ntasks-per-node, time, account, and partition for your site
##

#SBATCH --job-name=mpi-example
#SBATCH --account=your_account
#SBATCH --partition=compute
#SBATCH --time=02:00:00
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=32          # total tasks = nodes * ntasks-per-node
#SBATCH --cpus-per-task=1
#SBATCH --mem=0                        # use all memory on each node
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

mkdir -p logs

echo "Job started on $(date)"
echo "Nodes: ${SLURM_JOB_NUM_NODES}  Tasks: ${SLURM_NTASKS}"

module purge
module load gcc/12.2
module load openmpi/4.1

cd "$SLURM_SUBMIT_DIR"

# Optional: bind threads or disable SMT if required
# srun --hint=nomultithread --mpi=pmi2 ...

# Example MPI app. Replace with your binary and args.
# srun automatically launches one task per slot as set by Slurm.
srun ./bin/mpi_program --iterations 1000 --size 4096

echo "Job finished on $(date)"
