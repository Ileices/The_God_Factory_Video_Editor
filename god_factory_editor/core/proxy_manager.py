"""
ProxyManager — generates and caches low-resolution preview copies.
The proxy is used by the video player for smooth scrubbing of 4K content.
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

from god_factory_editor.config import PROXIES_DIR, settings
from god_factory_editor.utils.ffmpeg_wrapper import FFmpegWrapper, ffmpeg as _default_ff
from god_factory_editor.utils.logger import log


class _ProxySignals(QObject):
    progress = Signal(float)     # 0.0–1.0
    ready = Signal(Path)         # proxy path
    failed = Signal(str)         # error message


class _ProxyTask(QRunnable):
    def __init__(self, source: Path, output: Path, width: int, height: int,
                 ff: FFmpegWrapper):
        super().__init__()
        self.source = source
        self.output = output
        self.temp_output = output.with_name(output.name + ".part.mp4")
        self.width = width
        self.height = height
        self.ff = ff
        self.signals = _ProxySignals()
        self.setAutoDelete(True)

    def run(self):
        log.info(f"Generating proxy for {self.source.name} → {self.output.name}")
        try:
            self.output.parent.mkdir(parents=True, exist_ok=True)
            if self.temp_output.exists():
                self.temp_output.unlink(missing_ok=True)
        except Exception:
            pass

        ok = self.ff.generate_proxy(self.source, self.temp_output, self.width, self.height)
        if ok:
            info = self.ff.get_video_info(self.temp_output)
            has_video = bool(info and any(
                s.get("codec_type") == "video"
                for s in info.get("streams", [])
            ))
            if has_video:
                try:
                    self.temp_output.replace(self.output)
                except Exception as exc:
                    msg = f"Proxy finalize failed: {exc}"
                    log.warning(msg)
                    self.signals.failed.emit(msg)
                    return
                log.info("Proxy generation complete.")
                self.signals.ready.emit(self.output)
                return

        try:
            if self.temp_output.exists():
                self.temp_output.unlink(missing_ok=True)
        except Exception:
            pass

        msg = "Proxy generation failed."
        log.warning(msg)
        self.signals.failed.emit(msg)


class ProxyManager(QObject):
    """
    Background proxy generator.

    proxy_ready(proxy_path)  — emitted when a proxy has been created
    proxy_failed(message)    — emitted if generation fails
    """

    proxy_ready = Signal(Path)
    proxy_failed = Signal(str)

    def __init__(self, ff: Optional[FFmpegWrapper] = None, parent=None):
        super().__init__(parent)
        self._ff = ff or _default_ff
        self._pool = QThreadPool.globalInstance()
        self._cache: dict[str, Path] = {}   # source hash → proxy path
        self._active_sources: set[str] = set()

    # ── Public API ────────────────────────────────────────────────────────────
    def get_proxy_path(self, source: Path) -> Optional[Path]:
        """Return the proxy path if it already exists and is valid."""
        proxy = self._proxy_path_for(source)
        if self._is_valid(source, proxy):
            return proxy
        return None

    def ensure_proxy(self, source: Path):
        """
        Return the proxy immediately if it exists, otherwise start background
        generation and emit proxy_ready when done.
        """
        proxy = self._proxy_path_for(source)
        if self._is_valid(source, proxy):
            self.proxy_ready.emit(proxy)
            return

        try:
            if proxy.exists():
                proxy.unlink(missing_ok=True)
        except Exception:
            pass

        source_key = str(source.resolve())
        if source_key in self._active_sources:
            return
        self._active_sources.add(source_key)

        res = settings.get("proxy_resolution", [854, 480])
        task = _ProxyTask(source, proxy, res[0], res[1], self._ff)
        task.signals.ready.connect(lambda p, key=source_key: self._on_task_ready(key, p))
        task.signals.failed.connect(lambda msg, key=source_key: self._on_task_failed(key, msg))
        self._pool.start(task)

    def cleanup_old_proxies(self, max_age_days: int = 7):
        """Delete proxy files older than max_age_days."""
        import time
        cutoff = time.time() - max_age_days * 86400
        removed = 0
        for p in PROXIES_DIR.glob("*.mp4"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except Exception:
                pass
        if removed:
            log.info(f"Cleaned up {removed} old proxy file(s).")

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _proxy_path_for(source: Path) -> Path:
        h = hashlib.md5(str(source).encode()).hexdigest()[:12]
        return PROXIES_DIR / f"{source.stem}_{h}_480p.mp4"

    def _is_valid(self, source: Path, proxy: Path) -> bool:
        if not proxy.exists():
            return False
        if proxy.stat().st_size < 1024:
            return False
        # Invalidate if source is newer
        try:
            if source.stat().st_mtime > proxy.stat().st_mtime:
                return False
        except Exception:
            pass
        info = self._ff.get_video_info(proxy)
        if not info:
            return False
        has_video = any(s.get("codec_type") == "video" for s in info.get("streams", []))
        if not has_video:
            return False
        return True

    def _on_task_ready(self, source_key: str, proxy_path: Path):
        self._active_sources.discard(source_key)
        self.proxy_ready.emit(proxy_path)

    def _on_task_failed(self, source_key: str, message: str):
        self._active_sources.discard(source_key)
        self.proxy_failed.emit(message)
