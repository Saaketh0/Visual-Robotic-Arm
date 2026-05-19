#!/usr/bin/env python3
"""Compatibility wrapper for the canonical xarm_runtime synthetic publisher."""

import sys
from pathlib import Path

_RUNTIME_SRC = Path(__file__).resolve().parents[2] / "xarm_runtime" / "src"
if _RUNTIME_SRC.is_dir():
    sys.path.insert(0, str(_RUNTIME_SRC))

from xarm_runtime.synthetic_pixel_error_publisher import *  # noqa: F401,F403
from xarm_runtime.synthetic_pixel_error_publisher import main


if __name__ == "__main__":
    main()
