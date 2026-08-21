"""Compatibility launcher for the canonical Times of Chaos web admin.

New deployments should use ``python -m webadmin.server``. This file remains so
older shortcuts do not start the retired, unauthenticated prototype server.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    runpy.run_module("webadmin.server", run_name="__main__")
