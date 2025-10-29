
---

### `.github/copilot-instructions.md`
```markdown
# Copilot Instructions for our HPC cluster

You are assisting with HPC job scheduling on a Slurm cluster.

## Cluster facts
- Scheduler: Slurm
- Default account: `your_account`
- Default CPU partition: `compute`
- Default GPU partition: `gpu`
- Default walltime: `02:00:00`
- Max nodes per job: 4  (adjust if different)
- Common modules: `gcc/12.2`, `openmpi/4.1`, `cuda/12.3`, `python/3.10`

## File layout in this repo
- `scripts/job_template.sbatch`  Generic SBATCH template for single node CPU jobs
- `scripts/mpi_job.slurm`       Multi node MPI example that uses `srun`
- `scripts/gpu_training.slurm`  Single node GPU example with Conda and CUDA
- `examples/job_explanation.txt` High level explanation for the above scripts

## Conventions you should follow
- Prefer `srun` for launching parallel tasks on Slurm unless site policy requires `mpirun`
- Always set job name, time limit, partition, account, output, error, and resources
- Use `#SBATCH --gres=gpu:<count>` for GPU requests
- Load modules before running. Activate environments only after modules are loaded
- Use `${SLURM_CPUS_PER_TASK}` and `${SLURM_NTASKS}` where possible
- Suggest `--hint=nomultithread` if hyperthreading must be disabled
- For MPI jobs, rely on `srun` to set ranks and host mapping

## What to do when asked
- If asked to adapt a script, preserve SBATCH lines and only change resource values that the user calls out
- If asked to optimize, propose changes but keep a copy of the original lines as commented alternatives
- If a path is outside the current repo, ask the user to add it with `/add-dir /path` then reference with `@/path/to/file`
