#!/usr/bin/env python3
"""Freesound Connect launcher.

Kept as a thin shim so `python3 freesound_connect.py`, the PyInstaller
build scripts and old docs keep working — the app itself lives in the
`freesoundconnect/` package.
"""

import sys

try:
    import PySide6  # noqa: F401
except ImportError:
    sys.exit(
        "Freesound Connect needs PySide6.\n"
        "Install it with:  pip3 install PySide6\n"
        "(or:  pip3 install -r requirements.txt )"
    )

from freesoundconnect.app import main

if __name__ == "__main__":
    main()
