"""
Thumbnail generator — extracts a frame from a video and returns it as a QPixmap.
Uses a background thread to avoid blocking the UI.
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool
from PySide6.QtGui import QPixmap, QImage

from god_factory_editor.config import THUMBNAILS_DIR
from god_factory_editor.utils.ffmpeg_wrapper import ffmpeg
from god_factory_editor.utils.logger import log


class ThumbnailSignals(QObject):
    ready = Signal(str, QPixmap)   # clip_id, pixmap
    failed = Signal(str)           # clip_id


class ThumbnailTask(QRunnable):
    def __init__(self,
                 clip_id: str,
                 source: Path,
                 time_seconds: float,
                 width: int = 320,
                 height: int = 180):
        super().__init__()
        self.clip_id = clip_id
        self.source = source
        self.time_seconds = time_seconds
        self.width = width
        self.height = height
        self.signals = ThumbnailSignals()
        self.setAutoDelete(True)

    def run(self):
        out_path = _thumb_path(self.clip_id)
        try:
            if not out_path.exists():
                ok = ffmpeg.extract_frame(
                    self.source, self.time_seconds, out_path,
                    self.width, self.height,
                )
                if not ok:
                    self.signals.failed.emit(self.clip_id)
                    return

            pixmap = QPixmap(str(out_path))
            if pixmap.isNull():
                self.signals.failed.emit(self.clip_id)
            else:
                self.signals.ready.emit(self.clip_id, pixmap)
        except Exception as exc:
            log.warning(f"Thumbnail generation failed for {self.clip_id}: {exc}")
            self.signals.failed.emit(self.clip_id)


class ThumbnailGenerator(QObject):
    """Queue-based async thumbnail generator."""

    thumbnail_ready = Signal(str, QPixmap)  # clip_id, pixmap

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(2)

    def request(self,
                clip_id: str,
                source: Path,
                time_seconds: float,
                width: int = 320,
                height: int = 180):
        """Schedule thumbnail extraction for clip_id."""
        task = ThumbnailTask(clip_id, source, time_seconds, width, height)
        task.signals.ready.connect(self.thumbnail_ready)
        self._pool.start(task)

    def invalidate(self, clip_id: str):
        p = _thumb_path(clip_id)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def _thumb_path(clip_id: str) -> Path:
    return THUMBNAILS_DIR / f"{clip_id}.jpg"
