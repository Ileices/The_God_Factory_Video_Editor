"""
Time utility functions — formatting and parsing timecodes.
"""

from __future__ import annotations


def seconds_to_str(seconds: float, show_ms: bool = False) -> str:
    """Convert seconds to HH:MM:SS or HH:MM:SS.mmm string."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if show_ms:
        ms = int((seconds % 1) * 1000)
        return f"{h}:{m:02d}:{s:02d}.{ms:03d}"
    return f"{h}:{m:02d}:{s:02d}"


def seconds_to_short(seconds: float) -> str:
    """Short form: MM:SS for <1 hour, H:MM:SS for ≥1 hour."""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def str_to_seconds(ts: str) -> float:
    """Parse HH:MM:SS.mmm or MM:SS or bare seconds into float seconds."""
    ts = ts.strip()
    try:
        return float(ts)
    except ValueError:
        pass
    parts = ts.replace(",", ".").split(":")
    try:
        parts = [float(p) for p in parts]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return parts[0]
    except Exception:
        return 0.0


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def duration_label(seconds: float) -> str:
    """Human-readable duration like '4m 32s' or '1h 12m'."""
    if seconds < 0:
        return "0s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
