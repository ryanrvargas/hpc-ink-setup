from __future__ import annotations


# Static documentation snippets used by documentation plugins.
# This acts as a simple in-code knowledge base for common HPC tools.
#
# Each key represents a topic (ex: gaussian, cuda)
# Each value is a list of lines that will be formatted into plugin output.
#
# These are intentionally lightweight and deterministic:
# - no external dependencies
# - no runtime fetching
# - predictable output for testing and retrieval
DOC_SNIPPETS = {
    "gaussian": [
        # Title line (used as the header in plugin output)
        "Gaussian Usage Notes",
        # Body lines (concise, LLM-friendly guidance)
        "Load the Gaussian module before submitting the job.",
        "Request memory and wall time carefully in the Slurm script.",
        "Match Gaussian input resource expectations with the Slurm resource request.",
        "Use cluster-approved scheduler examples for Gaussian jobs when available.",
        "Check output logs for memory, scratch-space, and convergence-related failures.",
    ],
    "cuda": [
        # Title line
        "CUDA Usage Notes",
        # Body lines
        "Use a GPU-capable partition when submitting CUDA workloads.",
        "Request GPUs explicitly in the Slurm job script.",
        "Match the CUDA toolkit and driver environment expected on the cluster.",
        "Verify that required modules are loaded before launching the application.",
    ],
}


# This is intentionally structured to scale as more documentation plugins are added.
# Future expansion could include:
# - docs_slurm
# - docs_mpi
# - docs_python
# - cluster-specific documentation
#
# Keeping this centralized makes it easy to:
# - reuse across plugins
# - index for retrieval
# - keep documentation consistent
