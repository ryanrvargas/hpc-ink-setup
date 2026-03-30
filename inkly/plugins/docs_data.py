from __future__ import annotations

DOC_SNIPPETS = {
    "gaussian": [
        "Gaussian Usage Notes",
        "Load the Gaussian module before submitting the job.",
        "Request memory and wall time carefully in the Slurm script.",
        "Match Gaussian input resource expectations with the Slurm resource request.",
        "Use cluster-approved scheduler examples for Gaussian jobs when available.",
        "Check output logs for memory, scratch-space, and convergence-related failures.",
    ],
    "cuda": [
        "CUDA Usage Notes",
        "Use a GPU-capable partition when submitting CUDA workloads.",
        "Request GPUs explicitly in the Slurm job script.",
        "Match the CUDA toolkit and driver environment expected on the cluster.",
        "Verify that required modules are loaded before launching the application.",
    ],
}

# Later on we could expand this to include things such as docs_cuda, docs_slurm, docs_mpi, docs_python, etc.
