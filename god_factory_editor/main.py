"""
Application entry point for The God Factory Video Editor.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure the project root (parent of god_factory_editor/) is on sys.path so
# `import god_factory_editor` works whether we launch via .bat, python -m, or
# PyInstaller (which bundles _MEIPASS).
_HERE = Path(__file__).resolve().parent          # god_factory_editor/
_ROOT = _HERE.parent                              # project root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _resource_path(relative: str) -> Path:
    """Return the absolute path to a resource, works for dev and PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).parent.parent
    return base / relative


def main() -> None:
    # ── PySide6 high-DPI before QApplication ─────────────────────────────────
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
    os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "d3d11va,dxva2")

    from PySide6.QtWidgets import QApplication, QSplashScreen
    from PySide6.QtGui import QIcon, QPixmap, QFont
    from PySide6.QtCore import Qt

    app = QApplication(sys.argv)
    
    # Set application-wide default font with explicit valid point size
    default_font = QFont("Segoe UI", 10)
    default_font.setPointSize(10)  # Ensure explicitly set
    app.setFont(default_font)
    app.setApplicationName("The God Factory Video Editor")
    app.setOrganizationName("GodFactory")
    app.setOrganizationDomain("godfactory.local")

    # ── App icon ──────────────────────────────────────────────────────────────
    icon_path = _resource_path("resources/icons/app.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # ── Stylesheet ────────────────────────────────────────────────────────────
    qss_path = _resource_path("resources/styles/dark.qss")
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    # ── Crash handler ─────────────────────────────────────────────────────────
    from god_factory_editor.utils.logger import install_crash_handler
    install_crash_handler()

    # ── Splash screen ─────────────────────────────────────────────────────────
    splash_path = _resource_path("resources/icons/splash.png")
    splash = None
    if splash_path.exists():
        pix = QPixmap(str(splash_path))
        splash = QSplashScreen(pix, Qt.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()

    # ── Main window ───────────────────────────────────────────────────────────
    from god_factory_editor.gui.main_window import MainWindow
    window = MainWindow()
    window.show()

    if splash:
        splash.finish(window)

    # ── Handle file argument (e.g. double-clicked .gfve or video from explorer) ─
    if len(sys.argv) > 1:
        arg = Path(sys.argv[1])
        from god_factory_editor.config import PROJECT_EXTENSION
        from god_factory_editor.utils.file_utils import is_video_file
        if arg.exists():
            if arg.suffix.lower() == PROJECT_EXTENSION:
                window.open_project_path(arg)
            elif is_video_file(arg):
                window._load_video(arg)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
