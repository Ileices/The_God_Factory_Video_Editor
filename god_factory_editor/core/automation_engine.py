"""
AutomationEngine — one-click pipeline orchestration for long-form and short-form editing.

This module intentionally reuses existing app capabilities (effects_engine,
audio_enhancer, ffmpeg_wrapper) so automation stays modular and predictable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from god_factory_editor.core.audio_enhancer import AUDIO_PRESET_MAP
from god_factory_editor.core.effects_engine import effects_engine
from god_factory_editor.models.clip import Clip
from god_factory_editor.utils.ffmpeg_wrapper import ffmpeg as ff


AUTOMATION_PROFILES: list[dict] = [
    {
        "id": "stream_highlights",
        "label": "Stream -> Highlights (Long-form)",
        "description": "Detect downtime, keep best moments, apply retention defaults.",
    },
    {
        "id": "stream_shorts",
        "label": "Stream -> Shorts Pack",
        "description": "Generate short-form candidates with captions and punchy pacing.",
    },
    {
        "id": "audio_cleanup",
        "label": "Audio Cleanup On Existing Clips",
        "description": "Batch-apply voice-forward audio settings and loudness guidance.",
    },
]


@dataclass
class AutomationResult:
    clips: list[Clip] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)


class AutomationEngine:
    """Composable one-click automations built from existing engine modules."""

    def run(
        self,
        *,
        profile_id: str,
        source: Path,
        total_duration: float,
        existing_clips: Optional[list[Clip]] = None,
        silence_seconds: float = 10.0,
        freeze_seconds: float = 5.0,
        black_seconds: float = 1.5,
        min_keep_seconds: float = 6.0,
        max_clips: int = 40,
        short_target_seconds: float = 45.0,
        short_max_seconds: float = 59.0,
        generate_captions: bool = True,
        apply_transitions: bool = True,
        apply_sfx: bool = True,
        audio_preset_id: str = "voice_boost_light",
        decibel_gate_lufs: float = -34.0,
        analysis_start: float = 0.0,
        analysis_end: Optional[float] = None,
        exclude_ranges: Optional[list[tuple[float, float]]] = None,
        noise_floor_db: float = -38.0,
    ) -> AutomationResult:
        start = max(0.0, float(analysis_start))
        end = float(analysis_end) if analysis_end is not None else float(total_duration)
        end = max(start, min(float(total_duration), end))
        scope_duration = max(0.0, end - start)
        skip_ranges = self._normalize_ranges(exclude_ranges or [])

        if profile_id == "stream_highlights":
            return self._stream_to_highlights(
                source=source,
                total_duration=scope_duration,
                start_offset=start,
                exclude_ranges=skip_ranges,
                silence_seconds=silence_seconds,
                freeze_seconds=freeze_seconds,
                black_seconds=black_seconds,
                min_keep_seconds=min_keep_seconds,
                max_clips=max_clips,
                generate_captions=generate_captions,
                apply_transitions=apply_transitions,
                apply_sfx=apply_sfx,
                decibel_gate_lufs=decibel_gate_lufs,
                noise_floor_db=noise_floor_db,
            )

        if profile_id == "stream_shorts":
            return self._stream_to_shorts(
                source=source,
                total_duration=scope_duration,
                start_offset=start,
                exclude_ranges=skip_ranges,
                silence_seconds=silence_seconds,
                freeze_seconds=freeze_seconds,
                black_seconds=black_seconds,
                min_keep_seconds=min_keep_seconds,
                max_clips=max_clips,
                target_seconds=short_target_seconds,
                max_seconds=short_max_seconds,
                generate_captions=generate_captions,
                decibel_gate_lufs=decibel_gate_lufs,
                noise_floor_db=noise_floor_db,
            )

        if profile_id == "audio_cleanup":
            return self._audio_cleanup(
                source=source,
                clips=existing_clips or [],
                audio_preset_id=audio_preset_id,
            )

        return AutomationResult(
            warnings=[f"Unknown automation profile: {profile_id}"],
            summary_lines=["No changes were made."],
        )

    def scan_loudness_windows(
        self,
        *,
        source: Path,
        total_duration: float,
        window_seconds: float = 120.0,
        start_offset: float = 0.0,
        end_offset: Optional[float] = None,
    ) -> list[dict]:
        """Return windowed loudness analysis for decibel/LUFS driven workflows."""
        out: list[dict] = []
        window = max(10.0, float(window_seconds))
        start = max(0.0, float(start_offset))
        end = float(end_offset) if end_offset is not None else float(total_duration)
        end = max(start, min(float(total_duration), end))
        pos = start
        while pos < end:
            dur = min(window, end - pos)
            m = ff.detect_loudness(source, pos, dur)
            out.append(
                {
                    "start": round(pos, 3),
                    "end": round(pos + dur, 3),
                    "integrated_lufs": m.get("integrated_lufs"),
                    "true_peak_dbtp": m.get("true_peak_dbtp"),
                    "lra": m.get("lra"),
                }
            )
            pos += window
        return out

    def _stream_to_highlights(
        self,
        *,
        source: Path,
        total_duration: float,
        start_offset: float,
        exclude_ranges: list[tuple[float, float]],
        silence_seconds: float,
        freeze_seconds: float,
        black_seconds: float,
        min_keep_seconds: float,
        max_clips: int,
        generate_captions: bool,
        apply_transitions: bool,
        apply_sfx: bool,
        decibel_gate_lufs: float,
        noise_floor_db: float,
    ) -> AutomationResult:
        segments, boring = effects_engine.auto_plan_segments(
            source,
            total_duration,
            silence_seconds=silence_seconds,
            freeze_seconds=freeze_seconds,
            black_seconds=black_seconds,
            min_keep_seconds=min_keep_seconds,
            action="remove",
            speed_factor=8.0,
            noise_floor_db=noise_floor_db,
        )

        clips = [
            Clip(
                start_time=start_offset + s["start"],
                end_time=start_offset + s["end"],
                name=f"Highlight {i:02d}",
                tags=["auto", "highlight"],
            )
            for i, s in enumerate(segments, start=1)
            if s.get("kind") == "keep" and s["end"] > s["start"]
        ]

        clips = self._subtract_ranges_from_clips(clips, exclude_ranges)
        clips = self._filter_by_decibel_gate(source=source, clips=clips, min_lufs=decibel_gate_lufs)
        clips = self._limit_and_rank(source=source, clips=clips, max_clips=max_clips)

        stats = effects_engine.apply_retention_rules(
            clips,
            transition_min_clip_seconds=20.0,
            apply_sfx=apply_sfx,
            apply_transitions=apply_transitions,
            imply_slowmo_for_short_keep=False,
        )

        if generate_captions:
            for c in clips:
                c.captions = effects_engine.generate_auto_captions_for_clip(source, c, min_speech_seconds=0.8)

        removed = sum(max(0.0, r["end"] - r["start"]) for r in boring)
        return AutomationResult(
            clips=clips,
            summary_lines=[
                f"Generated {len(clips)} highlight clip(s).",
                f"Detected about {removed:.1f}s of boring downtime.",
                f"Transitions: {stats['transitions']} | SFX: {stats['sfx']}.",
            ],
        )

    def _stream_to_shorts(
        self,
        *,
        source: Path,
        total_duration: float,
        start_offset: float,
        exclude_ranges: list[tuple[float, float]],
        silence_seconds: float,
        freeze_seconds: float,
        black_seconds: float,
        min_keep_seconds: float,
        max_clips: int,
        target_seconds: float,
        max_seconds: float,
        generate_captions: bool,
        decibel_gate_lufs: float,
        noise_floor_db: float,
    ) -> AutomationResult:
        base = self._stream_to_highlights(
            source=source,
            total_duration=total_duration,
            start_offset=start_offset,
            exclude_ranges=exclude_ranges,
            silence_seconds=silence_seconds,
            freeze_seconds=freeze_seconds,
            black_seconds=black_seconds,
            min_keep_seconds=min_keep_seconds,
            max_clips=max_clips,
            generate_captions=generate_captions,
            apply_transitions=False,
            apply_sfx=True,
            decibel_gate_lufs=decibel_gate_lufs,
            noise_floor_db=noise_floor_db,
        )

        out: list[Clip] = []
        tgt = max(10.0, float(target_seconds))
        cap = max(tgt, float(max_seconds))
        short_idx = 1

        for c in base.clips:
            dur = c.duration
            if dur <= cap:
                c.name = f"Short {short_idx:02d}"
                c.tags.extend(["short", "vertical-ready"])
                c.transition_out = "none"
                c.speed = min(1.25, max(1.0, c.speed))
                out.append(c)
                short_idx += 1
                continue

            # Split very long keep clips into short-friendly chunks.
            s = c.start_time
            while s < c.end_time:
                e = min(c.end_time, s + tgt)
                if e - s < 8.0:
                    break
                sc = Clip(
                    start_time=s,
                    end_time=e,
                    name=f"Short {short_idx:02d}",
                    tags=["auto", "short", "vertical-ready"],
                )
                sc.speed = 1.05
                if generate_captions:
                    sc.captions = effects_engine.generate_auto_captions_for_clip(source, sc, min_speech_seconds=0.55)
                out.append(sc)
                short_idx += 1
                s = e

        out = self._limit_and_rank(source=source, clips=out, max_clips=max_clips)
        base.summary_lines.insert(0, f"Built {len(out)} shorts candidate(s).")
        base.clips = out
        return base

    def _audio_cleanup(self, *, source: Path, clips: list[Clip], audio_preset_id: str) -> AutomationResult:
        if not clips:
            return AutomationResult(
                warnings=["No clips available for audio cleanup."],
                summary_lines=["Create or import clips first, then rerun Audio Cleanup."],
            )

        preset = AUDIO_PRESET_MAP.get(audio_preset_id) or AUDIO_PRESET_MAP["voice_boost_light"]
        touched = 0
        for c in clips:
            c.audio_voice_boost = float(preset.get("voice_boost", 0.0))
            c.audio_game_duck = float(preset.get("game_duck", 0.0))
            c.audio_normalize = bool(preset.get("normalize", False))
            c.audio_denoise = bool(preset.get("denoise", False))
            c.tags.append("audio-cleanup")
            touched += 1

        return AutomationResult(
            clips=clips,
            summary_lines=[
                f"Applied audio preset '{preset['label']}' to {touched} clip(s).",
                "Export in Accurate mode for full audio filter fidelity.",
            ],
        )

    def _filter_by_decibel_gate(self, *, source: Path, clips: list[Clip], min_lufs: float) -> list[Clip]:
        out: list[Clip] = []
        for c in clips:
            sample = min(30.0, c.duration)
            if sample <= 1.0:
                continue
            loud = ff.detect_loudness(source, c.start_time, sample)
            lufs = loud.get("integrated_lufs")
            if lufs is None:
                out.append(c)
                continue
            # Keep if loud enough (less negative is louder).
            if lufs >= float(min_lufs):
                out.append(c)
        return out

    def _limit_and_rank(self, *, source: Path, clips: list[Clip], max_clips: int) -> list[Clip]:
        if len(clips) <= max_clips:
            return clips

        scored: list[tuple[float, Clip]] = []
        for c in clips:
            sample = min(20.0, c.duration)
            m = ff.detect_loudness(source, c.start_time, sample)
            lufs = m.get("integrated_lufs")
            # Score favors more energetic (louder) and medium-length segments.
            loud_score = 0.0 if lufs is None else (60.0 + float(lufs))
            dur_score = min(1.0, c.duration / 45.0)
            score = loud_score + dur_score
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [c for _, c in scored[: max(1, int(max_clips))]]
        selected.sort(key=lambda c: c.start_time)
        for i, c in enumerate(selected, start=1):
            if c.name.startswith("Highlight"):
                c.name = f"Highlight {i:02d}"
        return selected

    @staticmethod
    def _normalize_ranges(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
        cleaned = [(max(0.0, float(a)), max(0.0, float(b))) for a, b in ranges if b > a]
        cleaned.sort(key=lambda x: x[0])
        merged: list[tuple[float, float]] = []
        for a, b in cleaned:
            if not merged or a > merged[-1][1]:
                merged.append((a, b))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        return merged

    def _subtract_ranges_from_clips(self, clips: list[Clip], ranges: list[tuple[float, float]]) -> list[Clip]:
        if not ranges:
            return clips
        out: list[Clip] = []
        for c in clips:
            pieces = [(c.start_time, c.end_time)]
            for ra, rb in ranges:
                next_pieces: list[tuple[float, float]] = []
                for a, b in pieces:
                    if rb <= a or ra >= b:
                        next_pieces.append((a, b))
                        continue
                    if ra > a:
                        next_pieces.append((a, ra))
                    if rb < b:
                        next_pieces.append((rb, b))
                pieces = next_pieces
                if not pieces:
                    break
            for i, (a, b) in enumerate(pieces, start=1):
                if b - a < 0.8:
                    continue
                nc = c.copy()
                nc.start_time = a
                nc.end_time = b
                if len(pieces) > 1:
                    nc.name = f"{c.name} Part {i}"
                out.append(nc)
        return out


automation_engine = AutomationEngine()
