"""
File utilities — validation, sanitisation, supported formats.
"""

from __future__ import annotations
import re
import shutil
from pathlib import Path
from typing import Optional

SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".ts",
    ".m4v", ".webm", ".flv", ".wmv", ".mpg", ".mpeg",
    ".m2ts", ".mts", ".3gp", ".ogv", ".vob",
}

SUPPORTED_SUBTITLE_EXTENSIONS = {
    ".vtt",   # WebVTT (YouTube auto-captions)
    ".srt",   # SubRip
    ".sbv",   # YouTube SBV format
}


def is_video_file(path: Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def is_subtitle_file(path: Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_SUBTITLE_EXTENSIONS


def video_file_dialog_filter() -> str:
    """Build a Qt file dialog filter from supported extensions."""
    pattern = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_VIDEO_EXTENSIONS))
    return f"Video Files ({pattern});;All Files (*)"


def subtitle_file_dialog_filter() -> str:
    """Build a Qt file dialog filter for subtitle files."""
    pattern = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_SUBTITLE_EXTENSIONS))
    return f"Subtitle Files ({pattern});;All Files (*)"


def sanitise_filename(name: str) -> str:
    """Remove/replace characters that are invalid in Windows filenames."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip(". ")
    return name or "clip"


def ensure_unique_path(path: Path) -> Path:
    """If path exists, append a counter until the path is free."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    parent = path.parent
    i = 2
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def free_space_bytes(path: Path) -> int:
    """Return free bytes on the drive containing path."""
    try:
        usage = shutil.disk_usage(path)
        return usage.free
    except Exception:
        return 0


def estimate_export_size(duration_seconds: float, bitrate_bps: int) -> int:
    """Rough estimate of output file size in bytes."""
    return int(duration_seconds * bitrate_bps / 8)


def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} PB"
