#!/bin/bash
##
## Single node GPU job template for deep learning
## Adjust GPU count, partition, time, and memory for your site
##

#SBATCH --job-name=gpu-train
#SBATCH --account=your_account
#SBATCH --partition=gpu
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1                 # request 1 GPU (change to gpu:4 if needed)
#SBATCH --mem=32G
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

mkdir -p logs

echo "Job started on $(date)"
echo "Node: $SLURMD_NODENAME  GPUs: ${CUDA_VISIBLE_DEVICES}"

module purge
module load cuda/12.3
module load python/3.10
# If your site provides cudnn, nccl, or specific frameworks, load them too
# module load cudnn/8 nccl/2

cd "$SLURM_SUBMIT_DIR"

# Activate a Conda or venv environment if you use one
# Ensure the environment is created ahead of time
# Example with Conda:
# source ~/.bashrc
# conda activate dl-env

# Sanity check of GPU visibility
nvidia-smi || true

# Example PyTorch training call
python train.py \
  --data /path/to/data \
  --epochs 50 \
  --batch-size 64 \
  --num-workers "${SLURM_CPUS_PER_TASK}" \
  --log-dir "runs/${SLURM_JOB_NAME}-${SLURM_JOB_ID}"

echo "Job finished on $(date)"
