#!/usr/bin/env python3
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEF_FILE = REPO_ROOT / "Container" / "inkly.def"
OUT_SIF = REPO_ROOT / "Container" / "inkly.sif"

def main() -> int:
    if not DEF_FILE.exists():
        print(f"Missing def file: {DEF_FILE}", file=sys.stderr)
        return 2

    apptainer = shutil.which("apptainer") or shutil.which("singularity")
    if not apptainer:
        print("Missing apptainer/singularity on PATH.", file=sys.stderr)
        return 2

    cmd = [apptainer, "build", str(OUT_SIF), str(DEF_FILE)]

    print("-> " + " ".join(cmd))
    return subprocess.call(cmd)

if __name__ == "__main__":
    raise SystemExit(main())
