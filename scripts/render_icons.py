#!/usr/bin/env python3
"""Regenerate assets/icon.png, .icns, and .ico from assets/icon.svg.

Usage:  python3 scripts/render_icons.py
Needs:  PySide6, Pillow; macOS for the .icns step (uses iconutil).
"""

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "assets", "icon.svg")
SIZES = (16, 32, 48, 64, 128, 256, 512, 1024)

# (iconset filename, source size)
ICONSET_MAP = [
    ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
]


def render_pngs(out_dir):
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    QGuiApplication(sys.argv)
    renderer = QSvgRenderer(SVG)
    if not renderer.isValid():
        sys.exit("Could not parse %s" % SVG)
    paths = {}
    for size in SIZES:
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        paths[size] = os.path.join(out_dir, "icon-%d.png" % size)
        img.save(paths[size])
    return paths


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    with tempfile.TemporaryDirectory() as tmp:
        pngs = render_pngs(tmp)

        shutil.copy(pngs[256], os.path.join(ROOT, "assets", "icon.png"))

        from PIL import Image
        Image.open(pngs[256]).save(
            os.path.join(ROOT, "assets", "icon.ico"),
            sizes=[(s, s) for s in SIZES if s <= 256])

        if sys.platform == "darwin":
            iconset = os.path.join(tmp, "icon.iconset")
            os.makedirs(iconset)
            for name, size in ICONSET_MAP:
                shutil.copy(pngs[size], os.path.join(iconset, name))
            subprocess.run(
                ["iconutil", "-c", "icns", iconset,
                 "-o", os.path.join(ROOT, "assets", "icon.icns")],
                check=True)
        else:
            print("Skipping .icns (needs macOS iconutil).")

    print("Icons regenerated in assets/.")


if __name__ == "__main__":
    main()
