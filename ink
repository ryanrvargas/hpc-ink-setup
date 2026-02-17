#!/usr/bin/env python3
"""
Ink CLI Wrapper

Purpose
-------
This file is the executable entrypoint for Inkly.

It is intentionally minimal and contains no runtime logic.
All real functionality lives in `ink_core.py`.

Responsibilities
----------------
1. Detect installed runtime layout under ~/.inkly
2. Inject ~/.inkly/lib into sys.path (if it exists)
3. Import and execute ink_core.main()

Why This Exists
---------------
We separate CLI execution from runtime logic so that:

- ink_core.py is fully importable (for testing and reuse)
- Unit tests can import runtime logic without installation
- The installed CLI can resolve modules correctly
- No runtime assumptions are enforced at import time

Important Ordering Rule
-----------------------
sys.path must be modified BEFORE importing ink_core.
If we import first, Python will fail to locate ink_core.
"""

import sys
from pathlib import Path
import os

# Bootstrap Installed Runtime Path
# In installed mode, Inkly runtime files live in:
#
#     ~/.inkly/lib/
#
# That directory contains:
#     - ink_core.py
#     - config.py
#
# When this wrapper runs from ~/.npm-global/bin,
# Python does NOT automatically know about ~/.inkly/lib.
#
# Therefore, we manually inject it into sys.path.

DEFAULT_INKLY_HOME = Path.home() / ".inkly"
LIB_DIR = DEFAULT_INKLY_HOME / "lib"

# Inject installed runtime directory BEFORE importing ink_core
if LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))

# Import Runtime Core (after path injection)
# This must happen AFTER modifying sys.path.
# Otherwise, Python will raise ModuleNotFoundError.
from inkly.ink_core import main


# The wrapper does nothing if INKLY_HOME_OVERRIDE is set.
# All CLI behavior is handled inside ink_core.main().
if __name__ == "__main__":
    sys.exit(main())