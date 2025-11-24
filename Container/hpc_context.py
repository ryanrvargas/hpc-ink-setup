#!/usr/bin/env python3
"""
hpc_context.py
Runs OUTSIDE the container.
Collects HPC/Slurm information and prints a JSON blob to stdout.
This JSON becomes stdin for the container's entrypoint.
"""

import json
import os
import subprocess

def run(cmd):
    "Run a command and return its output safely."
    # Execute the external command 'cmd', capture stdout and refirect stderr into stdout
    # text=True makes sure we get a string back instead of bytes
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except Exception as e:
        # On error, return the error message
        return f"ERROR running {cmd}: {e}"

def safe_read(path):
    "Read a file safely without crashing."
    try:
        # Open the file and read its contents
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        # On error, return the error message
        return f"ERROR reading {path}: {e}"

def main():
    # Collect HPC/Slurm context information
    # Store the collected data in a dictionary
    # Convert the dictionary to a JSON string and print it
    data = {
        "hostname": run(["hostname"]).strip(),
        "squeue": run(["squeue"]),
        "sinfo": run(["sinfo"]),
        "slurm_conf": safe_read("/etc/slurm/slurm.conf"),
        "environment": "\n".join([f"{k}={v}" for k, v in os.environ.items()])
    }
    # Print the JSON data to stdout for the container to consume as stdin
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
