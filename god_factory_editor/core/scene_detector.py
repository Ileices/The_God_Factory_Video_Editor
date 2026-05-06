"""
SceneDetector — runs PySceneDetect in a background thread to find scene cuts.
Falls back gracefully if scenedetect is not installed.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import QThread, Signal

from god_factory_editor.utils.logger import log


class SceneDetector(QThread):
    """
    Signals
    -------
    progress(percent)              — 0–100
    scenes_found(list_of_tuples)   — [(start_sec, end_sec), ...]
    failed(message)
    status(text)
    """

    progress = Signal(int)
    scenes_found = Signal(list)   # List[Tuple[float, float]]
    failed = Signal(str)
    status = Signal(str)

    def __init__(self,
                 video_path: Path,
                 threshold: float = 27.0,
                 min_scene_duration: float = 15.0,
                 parent=None):
        super().__init__(parent)
        self.video_path = Path(video_path)
        self.threshold = threshold
        self.min_scene_duration = min_scene_duration
        self._abort = False

    def cancel(self):
        self._abort = True

    # ── Thread body ───────────────────────────────────────────────────────────
    def run(self):
        try:
            from scenedetect import open_video, SceneManager
            from scenedetect.detectors import ContentDetector
        except ImportError:
            self.failed.emit(
                "PySceneDetect is not installed.\n"
                "Run setup.bat to install all dependencies."
            )
            return

        self.status.emit("Opening video for analysis…")
        self.progress.emit(0)

        try:
            video = open_video(str(self.video_path))
        except Exception as exc:
            self.failed.emit(f"Could not open video for scene detection:\n{exc}")
            return

        sm = SceneManager()
        sm.add_detector(ContentDetector(threshold=self.threshold))

        self.status.emit("Detecting scenes… this may take several minutes.")
        try:
            sm.detect_scenes(video=video, show_progress=False)
        except Exception as exc:
            self.failed.emit(f"Scene detection error:\n{exc}")
            return

        if self._abort:
            self.status.emit("Cancelled.")
            return

        self.progress.emit(90)
        scene_list = sm.get_scene_list()

        if not scene_list:
            self.failed.emit(
                "No scene changes detected.\n"
                "Try lowering the sensitivity threshold in Settings."
            )
            return

        # Convert to (start_sec, end_sec) tuples, filter by min duration
        scenes: List[Tuple[float, float]] = []
        for start_tc, end_tc in scene_list:
            s = start_tc.get_seconds()
            e = end_tc.get_seconds()
            if (e - s) >= self.min_scene_duration:
                scenes.append((s, e))

        self.progress.emit(100)
        self.status.emit(f"Found {len(scenes)} scene(s) (after filtering short segments).")
        log.info(f"Scene detection complete: {len(scenes)} usable scenes.")
        self.scenes_found.emit(scenes)
