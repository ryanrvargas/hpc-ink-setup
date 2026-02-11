#!/usr/bin/env python3
"""
Ink CLI Wrapper

This file intentionally contains no runtime logic.

It exists solely as an executable entrypoint that delegates
all behavior to ink_core.main().

Keeping this file minimal ensures:
- Importable runtime logic
- Clean unit testing
- Separation of CLI and core logic
"""

from ink_core import main
import sys

if __name__ == "__main__":
    sys.exit(main())