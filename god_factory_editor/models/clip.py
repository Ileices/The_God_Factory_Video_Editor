"""
Clip dataclass — represents one marked video segment.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class Clip:
    start_time: float          # seconds from video start
    end_time: float
    name: str = ""
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    difficulty: int = 3        # 1–5
    thumbnail_path: Optional[Path] = None
    export_status: str = "pending"    # pending | exported | failed
    export_path: Optional[Path] = None
    created_at: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # ── Effects ──────────────────────────────────────────────────────────────
    # Speed multiplier: 1.0 = normal, 2.0 = 2x fast, 0.5 = half speed.
    speed: float = 1.0

    # Transition applied at the OUT end of this clip (when concatenating).
    # Values: "none" | "fade" | "fadeblack" | "dissolve" | "wipeleft"
    #         | "wiperight" | "slideright" | "slideleft" | "zoom"
    transition_out: str = "none"
    transition_duration: float = 0.5  # seconds

    # Sound-effect events: [{"name": str, "offset": float, "volume": float}]
    # offset is seconds from clip start_time.
    sfx_events: List[dict] = field(default_factory=list)

    # Audio enhancement settings
    audio_voice_boost: float = 0.0    # dB extra gain on voice-freq band (0–12)
    audio_game_duck: float = 0.0      # dB to reduce low-freq game rumble (0–12)
    audio_normalize: bool = False     # loudness normalization (EBU R128)
    audio_denoise: bool = False       # AI noise reduction via arnndn

    # Picture adjustment settings
    picture_brightness: float = 0.0   # eq brightness: -1.0 to 1.0
    picture_contrast: float = 1.0     # eq contrast: 0.5 to 2.0
    picture_saturation: float = 1.0   # eq saturation: 0.0 to 3.0
    picture_gamma: float = 1.0        # eq gamma: 0.1 to 3.0
    picture_sharpen: float = 0.0      # unsharp intensity: 0.0 to 2.0

    # Caption events: [{"start": float, "end": float, "text": str,
    #                  "font": str, "effect": str}]
    # Times are relative to clip start_time.
    captions: List[dict] = field(default_factory=list)

    # ── Computed ──────────────────────────────────────────────────────────────
    @property
    def duration(self) -> float:
        return max(0.0, self.end_time - self.start_time)

    @property
    def duration_str(self) -> str:
        d = self.duration
        h = int(d // 3600)
        m = int((d % 3600) // 60)
        s = int(d % 60)
        ms = int((d % 1) * 10)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}.{ms}"
        return f"{m}:{s:02d}.{ms}"

    @property
    def start_str(self) -> str:
        return _fmt(self.start_time)

    @property
    def end_str(self) -> str:
        return _fmt(self.end_time)

    # ── Validation ────────────────────────────────────────────────────────────
    def validate(self) -> Tuple[bool, str]:
        if self.start_time < 0:
            return False, "Start time cannot be negative."
        if self.end_time <= self.start_time:
            return False, "End time must be after start time."
        if self.duration < 0.5:
            return False, "Clip must be at least 0.5 seconds long."
        if self.duration > 86400:
            return False, "Clip exceeds 24 hours — please shorten it."
        return True, ""

    # ── Serialisation ─────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start": self.start_time,
            "end": self.end_time,
            "name": self.name,
            "notes": self.notes,
            "tags": list(self.tags),
            "difficulty": self.difficulty,
            "thumbnail_path": str(self.thumbnail_path) if self.thumbnail_path else None,
            "export_status": self.export_status,
            "export_path": str(self.export_path) if self.export_path else None,
            "created_at": self.created_at.isoformat(),
            # effects
            "speed": self.speed,
            "transition_out": self.transition_out,
            "transition_duration": self.transition_duration,
            "sfx_events": list(self.sfx_events),
            "audio_voice_boost": self.audio_voice_boost,
            "audio_game_duck": self.audio_game_duck,
            "audio_normalize": self.audio_normalize,
            "audio_denoise": self.audio_denoise,
            "picture_brightness": self.picture_brightness,
            "picture_contrast": self.picture_contrast,
            "picture_saturation": self.picture_saturation,
            "picture_gamma": self.picture_gamma,
            "picture_sharpen": self.picture_sharpen,
            "captions": list(self.captions),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Clip":
        c = cls(
            start_time=float(d.get("start", 0)),
            end_time=float(d.get("end", 0)),
            name=d.get("name", ""),
            notes=d.get("notes", ""),
            tags=list(d.get("tags", [])),
            difficulty=int(d.get("difficulty", 3)),
            export_status=d.get("export_status", "pending"),
        )
        c.id = d.get("id", c.id)
        tp = d.get("thumbnail_path")
        c.thumbnail_path = Path(tp) if tp else None
        ep = d.get("export_path")
        c.export_path = Path(ep) if ep else None
        try:
            c.created_at = datetime.fromisoformat(d.get("created_at", ""))
        except Exception:
            pass
        # effects (backward-compat: missing keys get defaults)
        c.speed = float(d.get("speed", 1.0))
        c.transition_out = d.get("transition_out", "none")
        c.transition_duration = float(d.get("transition_duration", 0.5))
        c.sfx_events = list(d.get("sfx_events", []))
        c.audio_voice_boost = float(d.get("audio_voice_boost", 0.0))
        c.audio_game_duck = float(d.get("audio_game_duck", 0.0))
        c.audio_normalize = bool(d.get("audio_normalize", False))
        c.audio_denoise = bool(d.get("audio_denoise", False))
        c.picture_brightness = float(d.get("picture_brightness", 0.0))
        c.picture_contrast = float(d.get("picture_contrast", 1.0))
        c.picture_saturation = float(d.get("picture_saturation", 1.0))
        c.picture_gamma = float(d.get("picture_gamma", 1.0))
        c.picture_sharpen = float(d.get("picture_sharpen", 0.0))
        c.captions = list(d.get("captions", []))
        return c

    def copy(self) -> "Clip":
        c = Clip(
            start_time=self.start_time,
            end_time=self.end_time,
            name=self.name,
            notes=self.notes,
            tags=list(self.tags),
            difficulty=self.difficulty,
            thumbnail_path=self.thumbnail_path,
            export_status=self.export_status,
            export_path=self.export_path,
            created_at=self.created_at,
            speed=self.speed,
            transition_out=self.transition_out,
            transition_duration=self.transition_duration,
            sfx_events=list(self.sfx_events),
            audio_voice_boost=self.audio_voice_boost,
            audio_game_duck=self.audio_game_duck,
            audio_normalize=self.audio_normalize,
            audio_denoise=self.audio_denoise,
            picture_brightness=self.picture_brightness,
            picture_contrast=self.picture_contrast,
            picture_saturation=self.picture_saturation,
            picture_gamma=self.picture_gamma,
            picture_sharpen=self.picture_sharpen,
            captions=list(self.captions),
        )
        c.id = self.id
        return c


def _fmt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}.{ms:03d}"
    return f"{m:02d}:{s:02d}.{ms:03d}"
