"""
VideoMetadata dataclass — holds information extracted from a video file.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class VideoMetadata:
    path: Path
    duration: float = 0.0          # seconds
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""
    audio_codec: str = ""
    bitrate: int = 0               # bits/second
    file_size: int = 0             # bytes
    has_audio: bool = True
    proxy_path: Optional[Path] = None

    @property
    def resolution_str(self) -> str:
        if self.width and self.height:
            return f"{self.width}×{self.height}"
        return "Unknown"

    @property
    def duration_str(self) -> str:
        d = self.duration
        h = int(d // 3600)
        m = int((d % 3600) // 60)
        s = int(d % 60)
        return f"{h}:{m:02d}:{s:02d}"

    @property
    def file_size_str(self) -> str:
        size = self.file_size
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    @property
    def is_4k(self) -> bool:
        return self.width >= 3840 or self.height >= 2160

    @property
    def is_hd(self) -> bool:
        return self.width >= 1920 or self.height >= 1080

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "duration": self.duration,
            "resolution": [self.width, self.height],
            "fps": self.fps,
            "codec": self.codec,
            "audio_codec": self.audio_codec,
            "bitrate": self.bitrate,
            "file_size": self.file_size,
            "has_audio": self.has_audio,
            "proxy_path": str(self.proxy_path) if self.proxy_path else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VideoMetadata":
        res = d.get("resolution", [0, 0])
        m = cls(
            path=Path(d.get("path", "")),
            duration=float(d.get("duration", 0)),
            width=int(res[0]) if res else 0,
            height=int(res[1]) if len(res) > 1 else 0,
            fps=float(d.get("fps", 0)),
            codec=d.get("codec", ""),
            audio_codec=d.get("audio_codec", ""),
            bitrate=int(d.get("bitrate", 0)),
            file_size=int(d.get("file_size", 0)),
            has_audio=bool(d.get("has_audio", True)),
        )
        pp = d.get("proxy_path")
        m.proxy_path = Path(pp) if pp else None
        return m
