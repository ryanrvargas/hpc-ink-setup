#!/usr/bin/env python3
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
CONTAINER_DIR = REPO_ROOT / "Container"
DEF_FILE = CONTAINER_DIR / "inkly.def"
OUT_SIF = CONTAINER_DIR / "inkly.sif"


def main() -> int:
    if not DEF_FILE.exists():
        print(f"Missing def file: {DEF_FILE}", file=sys.stderr)
        return 2

    apptainer = shutil.which("apptainer") or shutil.which("singularity")
    if not apptainer:
        print("Missing apptainer/singularity on PATH.", file=sys.stderr)
        return 2

    cmd = [apptainer, "build", str(OUT_SIF.name), str(DEF_FILE.name)]

    print("-> " + " ".join(cmd))

    return subprocess.call(cmd, cwd=DEF_FILE.parent)


if __name__ == "__main__":
    raise SystemExit(main())
