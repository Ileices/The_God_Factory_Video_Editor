"""
External NLE project import.

Supported (best effort):
- CMX-style .edl
- FCPXML / XML interchange (.fcpxml / .xml)
- MLT-based projects (.mlt / .kdenlive)
- OpenShot project (.osp)
- Adobe Premiere .prproj (best-effort XML parse)

Notes:
- Proprietary formats without public interchange specs are not parsed directly.
- Users should export XML/EDL from source NLE for highest reliability.
"""

from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse


@dataclass
class ImportedSegment:
    start: float
    end: float
    name: str = ""
    source: Optional[Path] = None


@dataclass
class ExternalImportResult:
    segments: list[ImportedSegment] = field(default_factory=list)
    source_candidates: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    format_name: str = ""


def parse_external_project(path: Path) -> ExternalImportResult:
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".edl":
        return _parse_edl(path)
    if suffix in {".fcpxml", ".xml"}:
        # XML can be many schemas; try known parsers in order.
        return _parse_xml_auto(path)
    if suffix in {".kdenlive", ".mlt"}:
        return _parse_mlt(path, format_name="Kdenlive/MLT")
    if suffix == ".osp":
        return _parse_openshot(path)
    if suffix == ".prproj":
        return _parse_prproj(path)
    if suffix == ".vpd":
        return _parse_vpd(path)

    out = ExternalImportResult(format_name=suffix.lstrip(".").upper())
    out.warnings.append(
        "This project format is not currently parseable directly. "
        "Please export XML/EDL from your editor, then import that file."
    )
    return out


def _parse_xml_auto(path: Path) -> ExternalImportResult:
    text = path.read_text(encoding="utf-8", errors="replace")
    if "<fcpxml" in text:
        return _parse_fcpxml(path)
    if "<xmeml" in text or "<sequence" in text or "<clipitem" in text:
        return _parse_xmeml(path)

    # Unknown XML dialect: try generic XML timeline extraction.
    out = _parse_xmeml(path)
    if out.segments:
        out.format_name = out.format_name or "XML (generic)"
        return out

    out = ExternalImportResult(format_name="XML")
    out.warnings.append(
        "XML project detected but no recognizable timeline schema was found. "
        "If using Premiere/Resolve/FCP, export FCPXML/EDL for better compatibility."
    )
    return out


def _parse_fcpxml(path: Path) -> ExternalImportResult:
    out = ExternalImportResult(format_name="FCPXML")
    root = ET.parse(path).getroot()

    asset_src: dict[str, Path] = {}
    for asset in root.findall(".//asset"):
        aid = asset.get("id")
        src = asset.get("src") or ""
        if aid and src:
            p = _path_from_url_or_text(src)
            if p:
                asset_src[aid] = p
                out.source_candidates.append(p)

    for i, ac in enumerate(root.findall(".//asset-clip"), start=1):
        ref = ac.get("ref") or ""
        start_t = _parse_fcpx_time(ac.get("start") or "0s")
        dur_t = _parse_fcpx_time(ac.get("duration") or "0s")
        end_t = start_t + dur_t
        if end_t <= start_t:
            continue
        name = (ac.get("name") or f"Imported Clip {i:02d}").strip()
        out.segments.append(
            ImportedSegment(
                start=max(0.0, start_t),
                end=max(0.0, end_t),
                name=name,
                source=asset_src.get(ref),
            )
        )

    return out


def _parse_xmeml(path: Path) -> ExternalImportResult:
    out = ExternalImportResult(format_name="XML (xmeml/FCP7/Premiere export)")
    root = ET.parse(path).getroot()

    # Try to infer fps from first available sequence rate.
    fps = 30.0
    tb = root.find(".//sequence/rate/timebase")
    if tb is not None:
        try:
            fps = float((tb.text or "30").strip())
        except Exception:
            fps = 30.0

    for i, clipitem in enumerate(root.findall(".//clipitem"), start=1):
        # Source bounds (in/out frames) are the most reliable for extracted clip content.
        in_el = clipitem.find("in")
        out_el = clipitem.find("out")
        if in_el is None or out_el is None:
            continue
        try:
            src_in = float((in_el.text or "0").strip()) / fps
            src_out = float((out_el.text or "0").strip()) / fps
        except Exception:
            continue
        if src_out <= src_in:
            continue

        name = (clipitem.findtext("name") or f"Imported Clip {i:02d}").strip()

        src_path = None
        pathurl = clipitem.findtext("file/pathurl")
        if pathurl:
            src_path = _path_from_url_or_text(pathurl)
            if src_path:
                out.source_candidates.append(src_path)

        out.segments.append(
            ImportedSegment(start=max(0.0, src_in), end=max(0.0, src_out), name=name, source=src_path)
        )

    return out


def _parse_mlt(path: Path, format_name: str = "MLT") -> ExternalImportResult:
    out = ExternalImportResult(format_name=format_name)
    root = ET.parse(path).getroot()

    producer_src: dict[str, Path] = {}
    for prod in root.findall(".//producer"):
        pid = prod.get("id")
        if not pid:
            continue
        for prop in prod.findall("property"):
            if (prop.get("name") or "") == "resource":
                p = _path_from_url_or_text((prop.text or "").strip())
                if p:
                    producer_src[pid] = p
                    out.source_candidates.append(p)

    idx = 1
    for playlist in root.findall(".//playlist"):
        for entry in playlist.findall("entry"):
            pid = entry.get("producer") or ""
            i_tc = entry.get("in") or "0"
            o_tc = entry.get("out") or "0"
            src_in = _parse_timecode_flexible(i_tc)
            src_out = _parse_timecode_flexible(o_tc)
            if src_out <= src_in:
                continue
            out.segments.append(
                ImportedSegment(
                    start=max(0.0, src_in),
                    end=max(0.0, src_out),
                    name=f"Imported Clip {idx:02d}",
                    source=producer_src.get(pid),
                )
            )
            idx += 1

    return out


def _parse_openshot(path: Path) -> ExternalImportResult:
    out = ExternalImportResult(format_name="OpenShot (.osp)")
    root = ET.parse(path).getroot()

    # OpenShot XML schemas vary. Parse clip-like nodes heuristically.
    idx = 1
    for node in root.iter():
        if node.tag.lower().endswith("clip"):
            data = {child.tag.lower(): (child.text or "").strip() for child in list(node)}
            start = _safe_float(data.get("start", ""))
            end = _safe_float(data.get("end", ""))
            if end <= start:
                # Some variants store position + duration.
                pos = _safe_float(data.get("position", ""))
                dur = _safe_float(data.get("duration", ""))
                start, end = pos, pos + dur
            if end <= start:
                continue

            src = data.get("path") or data.get("resource") or data.get("file") or ""
            src_path = _path_from_url_or_text(src) if src else None
            if src_path:
                out.source_candidates.append(src_path)

            name = data.get("name") or f"Imported Clip {idx:02d}"
            out.segments.append(
                ImportedSegment(start=max(0.0, start), end=max(0.0, end), name=name, source=src_path)
            )
            idx += 1

    if not out.segments:
        out.warnings.append(
            "Could not find clip timing blocks in this OpenShot project variant. "
            "Try exporting EDL/XML from the source editor."
        )
    return out


def _parse_prproj(path: Path) -> ExternalImportResult:
    # Premiere .prproj can be XML-like; some variants may be compressed.
    out = ExternalImportResult(format_name="Adobe Premiere (.prproj)")

    text = None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        text = None

    tmp_xml = path
    cleanup_tmp = None
    if text is None or ("<" not in text[:5000] and "<?xml" not in text[:5000]):
        # Try gzip decode variant.
        try:
            raw = gzip.decompress(path.read_bytes())
            txt = raw.decode("utf-8", errors="replace")
            cleanup_tmp = path.with_suffix(path.suffix + ".tmp.xml")
            cleanup_tmp.write_text(txt, encoding="utf-8")
            tmp_xml = cleanup_tmp
        except Exception:
            out.warnings.append(
                "Premiere project appears to be in a proprietary/internal format. "
                "In Premiere, export EDL or Final Cut Pro XML for robust import."
            )
            return out

    try:
        parsed = _parse_xml_auto(tmp_xml)
        parsed.format_name = "Adobe Premiere (.prproj/XML)"
        if not parsed.segments:
            parsed.warnings.append(
                "No clip segments could be extracted from this Premiere project directly. "
                "Export FCPXML/EDL from Premiere for better compatibility."
            )
        return parsed
    finally:
        if cleanup_tmp is not None and cleanup_tmp.exists():
            try:
                cleanup_tmp.unlink()
            except Exception:
                pass


def _parse_vpd(path: Path) -> ExternalImportResult:
    """Parse VideoProc Vlogger .vpd JSON project files.

    Video track timing: seconds.
    Subtitle/title track timing: milliseconds (divide by 1000).
    """
    import json

    out = ExternalImportResult(format_name="VideoProc Vlogger (.vpd)")
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        out.warnings.append(f"Could not read .vpd file: {exc}")
        return out

    # Build resid -> source path map from videolist
    res_map: dict[str, Path] = {}
    videolist = data.get("videolist") or {}
    for item in videolist.get("subitems") or []:
        uid = (item.get("uuid") or "").strip()
        src = (item.get("path") or "").strip()
        if uid and src:
            p = _path_from_url_or_text(src)
            if p:
                res_map[uid] = p
                out.source_candidates.append(p)

    timeline = data.get("timeline") or {}
    all_tracks = timeline.get("subitems") or []

    # --- Title/caption extraction from SubtitleTrack (TextEffectBlocks) ---
    # SubtitleTrack tstart/tduration are in MILLISECONDS; divide by 1000 for seconds.
    class _TitleCard:
        def __init__(self, timeline_start: float, timeline_end: float, text: str):
            self.timeline_start = timeline_start
            self.timeline_end = timeline_end
            self.text = text

    title_cards: list[_TitleCard] = []
    for track in all_tracks:
        if (track.get("type") or "") not in {"SubtitleTrack", "OverlayTrack"}:
            continue
        for block in (track.get("subitems") or []):
            if (block.get("type") or "") not in {"TextEffectBlock", "TextBlock", "TitleBlock"}:
                continue
            ts_ms = float(block.get("tstart") or 0.0)
            td_ms = float(block.get("tduration") or 0.0)
            ts = ts_ms / 1000.0
            te = ts + td_ms / 1000.0
            # Collect all dialogue texts
            texts: list[str] = []
            for dlg in (block.get("attribute") or {}).get("dialogues") or []:
                t = (dlg.get("text") or "").strip()
                if t:
                    texts.append(t)
            text = " | ".join(texts)
            if text:
                title_cards.append(_TitleCard(ts, te, text))

    def _best_title_for_block(tl_start: float, tl_end: float) -> str:
        """Return the title card text whose window best overlaps with this block's output timeline range."""
        best_text = ""
        best_overlap = 0.0
        for tc in title_cards:
            overlap = max(0.0, min(tl_end, tc.timeline_end) - max(tl_start, tc.timeline_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_text = tc.text
        return best_text

    # --- Video block extraction ---
    main_track = next(
        (t for t in all_tracks if (t.get("type") or "") == "MainVideoTrack"),
        None,
    )
    if main_track is None:
        out.warnings.append("No MainVideoTrack found in .vpd project.")
        return out

    blocks = [
        b for b in (main_track.get("subitems") or [])
        if (b.get("type") or "") == "MediaFileBlock"
    ]

    for i, block in enumerate(blocks, start=1):
        resid = (block.get("resid") or "").strip()
        src_path = res_map.get(resid)

        # Timeline position (output) — seconds
        tl_start = float(block.get("tstart") or 0.0)
        tl_dur = float(block.get("tduration") or 0.0)
        tl_end = tl_start + tl_dur

        # Source in/out — prefer SpeedAttribute (most accurate after speed changes)
        src_start: float = 0.0
        src_duration: float = 0.0
        try:
            speed_base = block["attribute"]["SpeedAttribute"]["Speed"]["baseData"]
            cs = float(speed_base.get("fileCuttedStart") or 0.0)
            cd = float(speed_base.get("fileCuttedDuration") or 0.0)
            if cd > 0:
                src_start = cs
                src_duration = cd
        except (KeyError, TypeError, ValueError):
            pass

        if src_duration <= 0:
            # Fallback to timeline duration
            src_start = tl_start
            src_duration = tl_dur

        if src_duration <= 0:
            continue

        # Use matching title card text as clip name, fallback to sequence number
        clip_title = _best_title_for_block(tl_start, tl_end)
        if not clip_title:
            clip_title = f"Clip {i:02d}"

        out.segments.append(
            ImportedSegment(
                start=max(0.0, src_start),
                end=max(0.0, src_start + src_duration),
                name=clip_title,
                source=src_path,
            )
        )

    if title_cards:
        out.warnings.append(
            f"Found {len(title_cards)} title/caption overlay(s): "
            + "; ".join(f'"{tc.text}"' for tc in title_cards[:5])
            + ("…" if len(title_cards) > 5 else "")
            + " — text overlays have been used as clip names where they overlap."
        )

    out.warnings.append(
        "NOTE: VideoProc Vlogger effects (color grading, transitions, overlays, "
        "speed ramps, animations) cannot be reproduced in this editor — they live "
        "inside VideoProc's rendering pipeline. To preserve all your effects, "
        "export the finished video from VideoProc first, then load that MP4 here."
    )

    if not out.segments:
        out.warnings.append(
            "No video clip blocks were found in this VideoProc Vlogger project."
        )
    return out


def _parse_edl(path: Path) -> ExternalImportResult:
    out = ExternalImportResult(format_name="EDL (CMX-style)")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    # Minimal CMX-like parse:
    # 001  AX       V     C        00:00:00:00 00:00:10:00 01:00:00:00 01:00:10:00
    event_re = re.compile(
        r"^\s*\d+\s+\S+\s+\S+\s+\S+\s+"
        r"(?P<src_in>\d\d:\d\d:\d\d[:;]\d\d)\s+"
        r"(?P<src_out>\d\d:\d\d:\d\d[:;]\d\d)\s+"
        r"(?P<rec_in>\d\d:\d\d:\d\d[:;]\d\d)\s+"
        r"(?P<rec_out>\d\d:\d\d:\d\d[:;]\d\d)"
    )

    idx = 1
    for line in lines:
        m = event_re.match(line)
        if not m:
            continue
        src_in = _parse_timecode_flexible(m.group("src_in"), fps=30.0)
        src_out = _parse_timecode_flexible(m.group("src_out"), fps=30.0)
        if src_out <= src_in:
            continue
        out.segments.append(
            ImportedSegment(start=src_in, end=src_out, name=f"EDL Clip {idx:02d}")
        )
        idx += 1

    if not out.segments:
        out.warnings.append(
            "No CMX-style events found. EDL dialects vary; if this fails, export XML/FCPXML instead."
        )
    return out


def _safe_float(text: str) -> float:
    try:
        return float((text or "").strip())
    except Exception:
        return 0.0


def _parse_fcpx_time(value: str) -> float:
    # FCPXML times like "1001/30000s" or "12s"
    v = (value or "").strip().lower().rstrip("s")
    if not v:
        return 0.0
    if "/" in v:
        a, b = v.split("/", 1)
        try:
            return float(a) / float(b)
        except Exception:
            return 0.0
    try:
        return float(v)
    except Exception:
        return 0.0


def _parse_timecode_flexible(tc: str, fps: float = 30.0) -> float:
    t = (tc or "").strip()
    if not t:
        return 0.0

    # HH:MM:SS:FF or HH:MM:SS;FF
    m = re.match(r"^(\d\d):(\d\d):(\d\d)[:;](\d\d)$", t)
    if m:
        hh, mm, ss, ff = map(int, m.groups())
        return hh * 3600 + mm * 60 + ss + (ff / max(1.0, fps))

    # HH:MM:SS.mmm or MM:SS.mmm
    if ":" in t:
        parts = t.replace(",", ".").split(":")
        try:
            if len(parts) == 3:
                hh = float(parts[0])
                mm = float(parts[1])
                ss = float(parts[2])
                return hh * 3600 + mm * 60 + ss
            if len(parts) == 2:
                mm = float(parts[0])
                ss = float(parts[1])
                return mm * 60 + ss
        except Exception:
            return 0.0

    try:
        return float(t)
    except Exception:
        return 0.0


def _path_from_url_or_text(text: str) -> Optional[Path]:
    raw = (text or "").strip()
    if not raw:
        return None

    # Premiere/FCP often use file:// URLs.
    if raw.startswith("file://"):
        try:
            u = urlparse(raw)
            p = unquote(u.path or "")
            # Windows drive normalization (/C:/...)
            if re.match(r"^/[A-Za-z]:/", p):
                p = p[1:]
            return Path(p)
        except Exception:
            return None

    # Some formats wrap path in URI-like text, fallback to direct path.
    raw = raw.strip('"')
    if not raw:
        return None
    return Path(raw)
