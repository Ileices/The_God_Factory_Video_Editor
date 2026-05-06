"""
Subtitle file parser — supports .vtt, .srt, .sbv formats.
Converts subtitle files to caption event format: [{"start": float, "end": float, "text": str}]
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import List, Optional


def parse_subtitle_file(path: Path) -> List[dict]:
    """
    Parse a subtitle file (.vtt, .srt, or .sbv) into caption events.
    
    Args:
        path: Path to subtitle file
        
    Returns:
        List of caption events: [{"start": float, "end": float, "text": str}, ...]
        Times are in seconds (float).
    """
    if not path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {path}")
    
    suffix = path.suffix.lower()
    
    if suffix == ".vtt":
        return _parse_vtt(path)
    elif suffix == ".srt":
        return _parse_srt(path)
    elif suffix == ".sbv":
        return _parse_sbv(path)
    else:
        raise ValueError(f"Unsupported subtitle format: {suffix}")


def _timecode_to_seconds(tc: str) -> Optional[float]:
    """Convert timecode string to seconds. Handles multiple formats."""
    tc = tc.strip()
    
    # VTT format: HH:MM:SS.mmm or MM:SS.mmm
    # SRT format: HH:MM:SS,mmm (comma instead of dot)
    # SBV format: HH:MM:SS.mmm
    
    # Normalize comma to dot for milliseconds
    tc = tc.replace(",", ".")
    
    # Split on dot to handle fractional seconds
    parts = tc.split(".")
    if len(parts) > 2:
        return None
    
    time_part = parts[0]
    millis = float("0." + parts[1]) if len(parts) == 2 else 0.0
    
    # Parse time component (HH:MM:SS or MM:SS)
    time_components = time_part.split(":")
    if len(time_components) == 3:
        # HH:MM:SS
        try:
            hours = int(time_components[0])
            minutes = int(time_components[1])
            seconds = int(time_components[2])
            return hours * 3600 + minutes * 60 + seconds + millis
        except ValueError:
            return None
    elif len(time_components) == 2:
        # MM:SS
        try:
            minutes = int(time_components[0])
            seconds = int(time_components[1])
            return minutes * 60 + seconds + millis
        except ValueError:
            return None
    
    return None


def _extract_vtt_timecode(tc: str) -> Optional[float]:
    """Extract the timestamp token from a WebVTT cue side, ignoring cue settings."""
    token = (tc or "").strip().split()[0] if tc and tc.strip() else ""
    if not token:
        return None
    return _timecode_to_seconds(token)


def _parse_vtt(path: Path) -> List[dict]:
    """Parse WebVTT (.vtt) file format."""
    content = path.read_text(encoding="utf-8", errors="replace")
    captions = []
    
    # Remove BOM if present
    if content.startswith("\ufeff"):
        content = content[1:]
    
    lines = content.split("\n")
    i = 0
    
    # Skip WEBVTT header and any file metadata
    while i < len(lines) and (not lines[i].strip() or lines[i].startswith("WEBVTT") or lines[i].startswith("NOTE")):
        i += 1
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for timecode line
        if "-->" in line:
            # Parse timecode: start --> end
            parts = line.split("-->")
            if len(parts) == 2:
                start = _extract_vtt_timecode(parts[0])
                end = _extract_vtt_timecode(parts[1])
                
                if start is not None and end is not None:
                    # Collect text lines until blank line or next timecode
                    text_lines = []
                    i += 1
                    while i < len(lines):
                        text_line = lines[i].strip()
                        if not text_line or "-->" in text_line:
                            break
                        # Remove VTT style/cue identifiers
                        if not text_line.startswith("NOTE"):
                            text_lines.append(text_line)
                        i += 1
                    
                    text = " ".join(text_lines).strip()
                    if text:
                        captions.append({
                            "start": start,
                            "end": end,
                            "text": text,
                        })
                    continue
        
        i += 1
    
    return captions


def _parse_srt(path: Path) -> List[dict]:
    """Parse SubRip (.srt) file format."""
    content = path.read_text(encoding="utf-8", errors="replace")
    captions = []
    
    # Remove BOM if present
    if content.startswith("\ufeff"):
        content = content[1:]
    
    lines = content.split("\n")
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for sequence number (should be numeric)
        if line and line.isdigit():
            # Next line should be timecode
            i += 1
            if i < len(lines):
                timecode_line = lines[i].strip()
                if "-->" in timecode_line:
                    parts = timecode_line.split("-->")
                    if len(parts) == 2:
                        start = _timecode_to_seconds(parts[0])
                        end = _timecode_to_seconds(parts[1])
                        
                        if start is not None and end is not None:
                            # Collect text lines until blank line
                            text_lines = []
                            i += 1
                            while i < len(lines):
                                text_line = lines[i].strip()
                                if not text_line:
                                    break
                                text_lines.append(text_line)
                                i += 1
                            
                            text = " ".join(text_lines).strip()
                            if text:
                                captions.append({
                                    "start": start,
                                    "end": end,
                                    "text": text,
                                })
                            continue
        
        i += 1
    
    return captions


def _parse_sbv(path: Path) -> List[dict]:
    """Parse YouTube SBV (.sbv) file format."""
    content = path.read_text(encoding="utf-8", errors="replace")
    captions = []
    
    # Remove BOM if present
    if content.startswith("\ufeff"):
        content = content[1:]
    
    lines = content.split("\n")
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # SBV format: HH:MM:SS.mmm,HH:MM:SS.mmm
        # Text on next line(s)
        if line and "," in line and not line.startswith("#"):
            parts = line.split(",")
            if len(parts) == 2:
                start = _timecode_to_seconds(parts[0])
                end = _timecode_to_seconds(parts[1])
                
                if start is not None and end is not None:
                    # Collect text lines until blank line or next timecode
                    text_lines = []
                    i += 1
                    while i < len(lines):
                        text_line = lines[i].strip()
                        if not text_line:
                            # Blank line ends this caption
                            break
                        # Check if this looks like a timecode (don't include in text)
                        if "," in text_line and _timecode_to_seconds(text_line.split(",")[0]):
                            # Next caption's timecode, don't consume it
                            i -= 1
                            break
                        text_lines.append(text_line)
                        i += 1
                    
                    text = " ".join(text_lines).strip()
                    if text:
                        captions.append({
                            "start": start,
                            "end": end,
                            "text": text,
                        })
        
        i += 1
    
    return captions


def merge_captions(
    captions: List[dict],
    start_offset: float = 0.0,
    clip_start: float = 0.0,
    clip_end: Optional[float] = None,
) -> List[dict]:
    """
    Merge/align loaded captions to a clip timeframe.
    
    Args:
        captions: List of caption events from parsed file
        start_offset: Offset to add to all caption times (seconds, default 0)
        clip_start: Clip start time in the source video (seconds)
        clip_end: Clip end time in the source video (seconds); if None, no filtering
        
    Returns:
        List of captions adjusted to clip coordinates and filtered to clip bounds.
    """
    merged = []
    
    for caption in captions:
        start = caption["start"] + start_offset
        end = caption["end"] + start_offset
        
        # Filter to clip bounds if specified
        if clip_end is not None:
            if end < clip_start or start > clip_end:
                continue  # Completely outside clip
            
            # Clamp to clip bounds
            start = max(start, clip_start)
            end = min(end, clip_end)
        
        # Adjust to clip-local coordinates (relative to clip start)
        start_local = start - clip_start
        end_local = end - clip_start
        
        merged.append({
            "start": max(0, start_local),
            "end": max(0, end_local),
            "text": caption.get("text", "").strip(),
        })
    
    # Remove zero-duration captions
    merged = [c for c in merged if c["end"] > c["start"]]
    
    return merged
