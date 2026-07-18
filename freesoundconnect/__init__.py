"""Freesound Connect — standalone companion app for DaVinci Resolve.

Search freesound.org, preview sounds with a waveform, and drag them (or a
selected region of them) straight onto your DaVinci Resolve timeline.
"""

import os
import sys

APP_NAME = "Freesound Connect"
VERSION = "2.1.0"


def resource_path(*parts):
    """Resolve bundled files both from source and from a PyInstaller build."""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)
