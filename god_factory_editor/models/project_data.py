"""
Project save/load — serialises the full editor state to/from a .gfve JSON file.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from god_factory_editor.models.clip import Clip
from god_factory_editor.models.video_file import VideoMetadata
from god_factory_editor.config import APP_VERSION, PROJECT_EXTENSION
from god_factory_editor.utils.logger import log


class ProjectData:
    FORMAT_VERSION = "1.0"

    def __init__(self):
        self.video: Optional[VideoMetadata] = None
        self.clips: List[Clip] = []
        # UI state
        self.timeline_zoom: float = 10.0
        self.playhead_position: float = 0.0
        self.volume: float = 0.80
        self.proxy_enabled: bool = True
        self.selected_clip_ids: List[str] = []
        self.created: str = datetime.now(timezone.utc).isoformat()
        self.modified: str = self.created
        self.source_path: Optional[Path] = None   # where .gfve was last saved

    # ── Serialise ─────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "version": self.FORMAT_VERSION,
            "app_version": APP_VERSION,
            "app": "The God Factory Video Editor",
            "created": self.created,
            "modified": datetime.now(timezone.utc).isoformat(),
            "video": self.video.to_dict() if self.video else None,
            "clips": [c.to_dict() for c in self.clips],
            "ui_state": {
                "timeline_zoom": self.timeline_zoom,
                "playhead_position": self.playhead_position,
                "volume": self.volume,
                "proxy_enabled": self.proxy_enabled,
                "selected_clip_ids": list(self.selected_clip_ids),
            },
        }

    def save(self, path: Path) -> bool:
        try:
            path = Path(path)
            if path.suffix.lower() != PROJECT_EXTENSION:
                path = path.with_suffix(PROJECT_EXTENSION)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
            self.source_path = path
            log.debug(f"ProjectData saved: {path}")
            return True
        except Exception as exc:
            log.exception(f"ProjectData save failed for {path}: {exc}")
            return False

    # ── Deserialise ───────────────────────────────────────────────────────────
    @classmethod
    def load(cls, path: Path) -> "ProjectData":
        log.debug(f"ProjectData loading: {path}")
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        proj = cls()
        proj.source_path = Path(path)
        proj.created = raw.get("created", proj.created)
        proj.modified = raw.get("modified", proj.modified)

        if raw.get("video"):
            proj.video = VideoMetadata.from_dict(raw["video"])

        for cd in raw.get("clips", []):
            proj.clips.append(Clip.from_dict(cd))

        ui = raw.get("ui_state", {})
        proj.timeline_zoom = float(ui.get("timeline_zoom", proj.timeline_zoom))
        proj.playhead_position = float(ui.get("playhead_position", 0))
        proj.volume = float(ui.get("volume", 0.8))
        proj.proxy_enabled = bool(ui.get("proxy_enabled", True))
        proj.selected_clip_ids = list(ui.get("selected_clip_ids", []))
        log.debug(
            f"ProjectData loaded: {path} | clips={len(proj.clips)} | "
            f"has_video={proj.video is not None}"
        )

        return proj

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def is_project_file(path: Path) -> bool:
        return Path(path).suffix.lower() == PROJECT_EXTENSION
