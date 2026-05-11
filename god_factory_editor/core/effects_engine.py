"""
EffectsEngine — speed presets, transition definitions, sound-effect library,
and intelligent auto-placement of transitions and SFX.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple

from god_factory_editor.utils.logger import log
from god_factory_editor.config import settings

# ── Speed presets ──────────────────────────────────────────────────────────────
SPEED_PRESETS: list[dict] = [
    {"label": "0.25× Slow-mo (quarter speed)",   "value": 0.25},
    {"label": "0.5×  Slow-mo (half speed)",       "value": 0.5},
    {"label": "0.75× Slightly slowed",            "value": 0.75},
    {"label": "1×    Normal speed",               "value": 1.0},
    {"label": "1.25× Slightly faster",            "value": 1.25},
    {"label": "1.5×  Faster",                     "value": 1.5},
    {"label": "2×    Double speed",               "value": 2.0},
    {"label": "3×    Triple speed",               "value": 3.0},
    {"label": "4×    Quad speed",                 "value": 4.0},
    {"label": "8×    Hyper-lapse",                "value": 8.0},
    {"label": "12×   Super-lapse",                "value": 12.0},
    {"label": "16×   Mega-lapse",                 "value": 16.0},
    {"label": "32×   Ultra-lapse",                "value": 32.0},
]

# ── Transition presets ─────────────────────────────────────────────────────────
# xfade_name maps to FFmpeg xfade transition name.
TRANSITION_PRESETS: list[dict] = [
    {"id": "none",        "label": "None (hard cut)",       "xfade": "fade",      "has_xfade": False},
    {"id": "fade",        "label": "Fade",                  "xfade": "fade",      "has_xfade": True},
    {"id": "fadeblack",   "label": "Fade through Black",    "xfade": "fadeblack", "has_xfade": True},
    {"id": "dissolve",    "label": "Cross Dissolve",        "xfade": "dissolve",  "has_xfade": True},
    {"id": "wipeleft",    "label": "Wipe Left",             "xfade": "wipeleft",  "has_xfade": True},
    {"id": "wiperight",   "label": "Wipe Right",            "xfade": "wiperight", "has_xfade": True},
    {"id": "slideleft",   "label": "Slide Left",            "xfade": "slideleft", "has_xfade": True},
    {"id": "slideright",  "label": "Slide Right",           "xfade": "slideright","has_xfade": True},
    {"id": "zoom",        "label": "Zoom In",               "xfade": "zoomintr",  "has_xfade": True},
    {"id": "pixelize",    "label": "Pixelize",              "xfade": "pixelize",  "has_xfade": True},
    {"id": "circleopen",  "label": "Circle Open",           "xfade": "circleopen","has_xfade": True},
]

TRANSITION_LABELS: dict[str, str] = {t["id"]: t["label"] for t in TRANSITION_PRESETS}
TRANSITION_XFADE:  dict[str, str] = {t["id"]: t["xfade"]  for t in TRANSITION_PRESETS}

AUTO_CUT_PRESETS: list[dict] = [
    {
        "id": "balanced",
        "label": "Balanced boring-cut cleanup",
        "silence_seconds": 12.0,
        "freeze_seconds": 6.0,
        "black_seconds": 2.0,
        "min_keep_seconds": 8.0,
    },
    {
        "id": "aggressive",
        "label": "Aggressive dead-air removal",
        "silence_seconds": 6.0,
        "freeze_seconds": 4.0,
        "black_seconds": 1.0,
        "min_keep_seconds": 5.0,
    },
]

AUTO_EDIT_TEMPLATES: list[dict] = [
    {
        "id": "balanced",
        "label": "Balanced (safe defaults)",
        "silence_seconds": 10.0,
        "freeze_seconds": 5.0,
        "black_seconds": 1.5,
        "min_keep_seconds": 6.0,
        "action": "remove",
        "speed_factor": 8.0,
        "transition_min_clip_seconds": 20.0,
        "caption_min_speech_seconds": 0.8,
    },
    {
        "id": "retention",
        "label": "Retention Focus (faster pacing)",
        "silence_seconds": 6.0,
        "freeze_seconds": 3.5,
        "black_seconds": 1.0,
        "min_keep_seconds": 4.0,
        "action": "speedup",
        "speed_factor": 12.0,
        "transition_min_clip_seconds": 15.0,
        "caption_min_speech_seconds": 0.6,
    },
    {
        "id": "aggressive",
        "label": "Aggressive Cleanup",
        "silence_seconds": 4.0,
        "freeze_seconds": 2.5,
        "black_seconds": 0.8,
        "min_keep_seconds": 3.0,
        "action": "remove",
        "speed_factor": 16.0,
        "transition_min_clip_seconds": 12.0,
        "caption_min_speech_seconds": 0.5,
    },
]

MAGIC_EDIT_TEMPLATES: list[dict] = [
    {
        "id": "retention_shockcut",
        "label": "Retention Shockcut",
        "description": "Fast pacing, punchy transitions, clean voice-forward sound.",
        "speed": 1.2,
        "transition_out": "dissolve",
        "transition_duration": 0.35,
        "audio_voice_boost": 4.0,
        "audio_game_duck": 3.0,
        "audio_normalize": True,
        "audio_denoise": False,
        "picture_brightness": 0.04,
        "picture_contrast": 1.12,
        "picture_saturation": 1.08,
        "picture_gamma": 1.02,
        "picture_sharpen": 0.6,
    },
    {
        "id": "cinematic_darkops",
        "label": "Cinematic Dark Ops",
        "description": "Deeper shadows, richer contrast, slower dramatic pace.",
        "speed": 0.9,
        "transition_out": "fadeblack",
        "transition_duration": 0.55,
        "audio_voice_boost": 2.0,
        "audio_game_duck": 1.5,
        "audio_normalize": True,
        "audio_denoise": True,
        "picture_brightness": -0.02,
        "picture_contrast": 1.2,
        "picture_saturation": 0.9,
        "picture_gamma": 0.95,
        "picture_sharpen": 0.4,
    },
    {
        "id": "clarity_competitive",
        "label": "Clarity Competitive",
        "description": "Readable visuals for gameplay + subtle motion speedup.",
        "speed": 1.1,
        "transition_out": "fade",
        "transition_duration": 0.4,
        "audio_voice_boost": 3.0,
        "audio_game_duck": 2.0,
        "audio_normalize": True,
        "audio_denoise": False,
        "picture_brightness": 0.05,
        "picture_contrast": 1.05,
        "picture_saturation": 1.02,
        "picture_gamma": 1.05,
        "picture_sharpen": 0.8,
    },
]


# ── Sound-effect library ───────────────────────────────────────────────────────
# Each entry describes a bundled SFX. The file is generated by FFmpeg if the
# actual .wav doesn't exist yet (simple tone placeholders), or comes from the
# user's resources/sfx/ folder.
_SFX_DEFINITIONS: list[dict] = [
    {
        "id": "whoosh",
        "label": "Whoosh (fast cut)",
        "description": "Short air-whoosh sound, great on hard cuts or speed ramps.",
        "generate_cmd": (
            "sine=frequency=400:duration=0.25,"
            "volume=0.6,"
            "atempo=1.5"
        ),
    },
    {
        "id": "boom",
        "label": "Boom (impact)",
        "description": "Low boom, works well on title cards and big moments.",
        "generate_cmd": (
            "sine=frequency=60:duration=0.5"
        ),
    },
    {
        "id": "swoosh_up",
        "label": "Swoosh Up",
        "description": "Rising tone, good for going to menu/cutscene.",
        "generate_cmd": "sine=frequency=200:duration=0.4",
    },
    {
        "id": "ding",
        "label": "Ding (win/success)",
        "description": "Short bright ding for wins and positive moments.",
        "generate_cmd": "sine=frequency=1200:duration=0.15",
    },
    {
        "id": "tension_riser",
        "label": "Tension Riser",
        "description": "Subtle rising tension tone for dramatic moments.",
        "generate_cmd": "sine=frequency=300:duration=1.0",
    },
]


class EffectsEngine:
    """
    Manages the SFX library (generates placeholders on first use),
    auto-detects good transition and SFX placement points using
    audio silence detection, and provides helper methods for the UI.
    """

    def __init__(self, sfx_dir: Optional[Path] = None):
        from god_factory_editor.config import RESOURCES_DIR
        self._sfx_dir = sfx_dir or (RESOURCES_DIR / "sfx")
        self._sfx_dir.mkdir(parents=True, exist_ok=True)

    # ── SFX library ───────────────────────────────────────────────────────────
    @property
    def sfx_list(self) -> list[dict]:
        """Return all available SFX (bundled + user-imported), with paths."""
        results = []
        # Built-in generated effects
        for defn in _SFX_DEFINITIONS:
            path = self._sfx_dir / f"{defn['id']}.wav"
            results.append({
                "id": defn["id"],
                "label": defn["label"],
                "description": defn["description"],
                "path": path,
                "exists": path.exists(),
                "builtin": True,
            })
        # User-imported files
        for f in sorted(self._sfx_dir.iterdir()):
            if f.suffix.lower() in (".wav", ".mp3", ".aac", ".ogg", ".m4a"):
                if not any(d["id"] == f.stem for d in _SFX_DEFINITIONS):
                    results.append({
                        "id": f.stem,
                        "label": f.stem.replace("_", " ").title(),
                        "description": "User-imported sound effect",
                        "path": f,
                        "exists": True,
                        "builtin": False,
                    })
        return results

    def ensure_sfx(self, sfx_id: str) -> Optional[Path]:
        """Return the path to an SFX file, generating it if needed."""
        path = self._sfx_dir / f"{sfx_id}.wav"
        if path.exists():
            return path
        for defn in _SFX_DEFINITIONS:
            if defn["id"] == sfx_id:
                return self._generate_sfx(defn, path)
        return None

    def _generate_sfx(self, defn: dict, output: Path) -> Optional[Path]:
        """Generate a simple tone-based SFX placeholder using FFmpeg."""
        from god_factory_editor.utils.ffmpeg_wrapper import ffmpeg as ff
        args = [
            ff.ffmpeg, "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency=880:duration=0.3",
            "-c:a", "pcm_s16le",
            str(output),
        ]
        # Use the specific generate_cmd if safe (no shell injection)
        gen = defn.get("generate_cmd", "")
        if gen and all(c not in gen for c in (";", "&", "|", "`", "$")):
            args[5] = gen  # replace default lavfi input
        ok, _, _ = ff.run(args, timeout=15)
        if ok and output.exists():
            log.info(f"Generated SFX placeholder: {output.name}")
            return output
        return None

    # ── Magic templates ─────────────────────────────────────────────────────
    @property
    def magic_templates(self) -> list[dict]:
        return list(MAGIC_EDIT_TEMPLATES)

    def apply_magic_template(self, clip, template_id: str, adaptive: bool = True) -> tuple[bool, str]:
        template = next((t for t in MAGIC_EDIT_TEMPLATES if t["id"] == template_id), None)
        if not template:
            return False, f"Template not found: {template_id}"

        for key, value in template.items():
            if key in ("id", "label", "description"):
                continue
            setattr(clip, key, value)

        if adaptive:
            # Adaptive tune for very short clips: reduce transition duration.
            dur = max(0.01, float(getattr(clip, "duration", 0.0)))
            if dur < 3.0:
                clip.transition_duration = min(clip.transition_duration, max(0.15, dur * 0.2))

            # Adaptive tune for very long clips: slightly faster pacing.
            if dur > 45.0:
                clip.speed = min(max(clip.speed, 1.0), 1.35)

        return True, f"Applied template: {template['label']}"

    def recommend_magic_templates(self, clip) -> list[str]:
        """Simple recommendations to bridge creative choice gaps."""
        dur = max(0.0, float(getattr(clip, "duration", 0.0)))
        tags = {t.lower() for t in getattr(clip, "tags", [])}
        rec: list[str] = []

        if dur >= 30.0:
            rec.append("retention_shockcut")
        if dur <= 8.0:
            rec.append("clarity_competitive")
        if {"horror", "night", "stealth"}.intersection(tags):
            rec.append("cinematic_darkops")

        if not rec:
            rec = ["clarity_competitive"]
        return rec

    # ── Auto-placement ─────────────────────────────────────────────────────────
    def auto_suggest_transitions(
        self,
        source: Path,
        clips: list,
        prefer_silence_gaps: bool = True,
    ) -> list[dict]:
        """
        For each consecutive clip pair, suggest whether to add a transition.
        Returns list of {clip_id, transition, confidence, reason}.

        Strategy:
        - If gap between clip[i].end and clip[i+1].start is >= 0.5s → dissolve
          (the stream has a natural cut point here)
        - If clips are adjacent (≤0.1s gap), check audio: if the boundary is
          during silence → suggest fade; if mid-speech → suggest "none" (hard cut
          to preserve dialogue)
        - If clip has speed != 1.0 → suggest "wipeleft" for the ramp-up exit
        """
        from god_factory_editor.utils.ffmpeg_wrapper import ffmpeg as ff
        suggestions = []
        clips_sorted = sorted(clips, key=lambda c: c.start_time)

        for i, clip in enumerate(clips_sorted[:-1]):
            next_clip = clips_sorted[i + 1]
            gap = next_clip.start_time - clip.end_time

            # Clips with a large gap in the source → dissolve is natural
            if gap >= 0.5:
                suggestions.append({
                    "clip_id": clip.id,
                    "transition": "dissolve",
                    "duration": 0.5,
                    "confidence": "high",
                    "reason": f"Natural gap of {gap:.1f}s — dissolve recommended",
                })
                continue

            if not prefer_silence_gaps:
                suggestions.append({
                    "clip_id": clip.id,
                    "transition": "none",
                    "duration": 0.3,
                    "confidence": "low",
                    "reason": "Hard cut (no analysis requested)",
                })
                continue

            # Check if the last 0.5s of the clip is silent (safe to transition)
            check_start = max(clip.start_time, clip.end_time - 0.6)
            silences = ff.detect_silence(
                source, check_start, 0.6, noise_floor_db=-35.0, min_duration=0.2
            )
            if silences:
                suggestions.append({
                    "clip_id": clip.id,
                    "transition": "fade",
                    "duration": 0.4,
                    "confidence": "high",
                    "reason": "Silence detected at clip boundary — safe to fade",
                })
            else:
                # Mid-dialogue — hard cut to preserve speech
                suggestions.append({
                    "clip_id": clip.id,
                    "transition": "none",
                    "duration": 0.3,
                    "confidence": "high",
                    "reason": "Audio detected at boundary — keeping hard cut to preserve dialogue",
                })

        return suggestions

    def auto_suggest_sfx(
        self,
        clips: list,
    ) -> list[dict]:
        """
        Suggest sound effects for clips.
        - Speed > 2× → 'whoosh' at start
        - Speed 0.5× or less → no SFX (slow-mo usually keeps natural audio)
        - Hard-cut after silence → 'boom' at cut-in point
        Returns list of {clip_id, sfx_id, offset, volume}.
        """
        suggestions = []
        for clip in clips:
            if clip.speed >= 2.0:
                suggestions.append({
                    "clip_id": clip.id,
                    "sfx_id": "whoosh",
                    "offset": 0.0,
                    "volume": 0.7,
                    "reason": f"{clip.speed}× speed ramp — whoosh at entry",
                })
            if clip.transition_out in ("none",) and clip.speed == 1.0:
                suggestions.append({
                    "clip_id": clip.id,
                    "sfx_id": "boom",
                    "offset": max(0.0, clip.duration - 0.1),
                    "volume": 0.5,
                    "reason": "Hard cut ending — subtle boom",
                })
        return suggestions

    def auto_detect_boring_ranges(
        self,
        source: Path,
        total_duration: float,
        silence_seconds: float = 12.0,
        freeze_seconds: float = 6.0,
        black_seconds: float = 2.0,
        noise_floor_db: float = -38.0,
    ) -> list[dict]:
        """
        Detect long boring regions in the source stream.
        Returns [{start, end, kind, reason}].
        Uses a single combined ffmpeg pass (silence + freeze + black) so the
        video is decoded only once — 3× less CPU time for long files.
        """
        from god_factory_editor.utils.ffmpeg_wrapper import ffmpeg as ff

        silences, freezes, blacks = ff.detect_boring_combined(
            source, 0.0, total_duration,
            noise_floor_db=noise_floor_db,
            silence_min=silence_seconds,
            freeze_min=freeze_seconds,
            black_min=black_seconds,
        )

        boring: list[dict] = []

        for start, end in silences:
            boring.append({
                "start": start,
                "end": end,
                "kind": "silence",
                "reason": f"Long silence / no talking ({end - start:.1f}s)",
            })

        for start, end in freezes:
            boring.append({
                "start": start,
                "end": end,
                "kind": "freeze",
                "reason": f"Very low motion / frozen gameplay ({end - start:.1f}s)",
            })

        for start, end in blacks:
            boring.append({
                "start": start,
                "end": end,
                "kind": "black",
                "reason": f"Black/loading screen ({end - start:.1f}s)",
            })

        boring.sort(key=lambda r: (r["start"], r["end"]))
        merged: list[dict] = []
        for region in boring:
            if not merged or region["start"] > merged[-1]["end"] + 0.25:
                merged.append(region.copy())
                continue
            merged[-1]["end"] = max(merged[-1]["end"], region["end"])
            merged[-1]["kind"] += f"+{region['kind']}"
            merged[-1]["reason"] += f"; {region['reason']}"
        return merged

    def auto_build_keep_ranges(
        self,
        source: Path,
        total_duration: float,
        silence_seconds: float = 12.0,
        freeze_seconds: float = 6.0,
        black_seconds: float = 2.0,
        min_keep_seconds: float = 8.0,
        noise_floor_db: float = -38.0,
    ) -> tuple[list[tuple[float, float]], list[dict]]:
        """Return keep ranges that skip long boring sections."""
        boring = self.auto_detect_boring_ranges(
            source,
            total_duration,
            silence_seconds=silence_seconds,
            freeze_seconds=freeze_seconds,
            black_seconds=black_seconds,
            noise_floor_db=noise_floor_db,
        )
        keep_ranges: list[tuple[float, float]] = []
        cursor = 0.0
        for region in boring:
            if region["start"] - cursor >= min_keep_seconds:
                keep_ranges.append((round(cursor, 3), round(region["start"], 3)))
            cursor = max(cursor, region["end"])
        if total_duration - cursor >= min_keep_seconds:
            keep_ranges.append((round(cursor, 3), round(total_duration, 3)))
        return keep_ranges, boring

    def auto_plan_segments(
        self,
        source: Path,
        total_duration: float,
        *,
        silence_seconds: float,
        freeze_seconds: float,
        black_seconds: float,
        min_keep_seconds: float,
        action: str = "remove",
        speed_factor: float = 8.0,
        noise_floor_db: float = -38.0,
    ) -> tuple[list[dict], list[dict]]:
        """
        Build an edit plan.

        Returns:
          segments: [
            {
              "start": float,
              "end": float,
              "kind": "keep"|"boring",
              "speed": float,
              "name": str,
            }, ...
          ]
          boring_ranges: output of auto_detect_boring_ranges
        """
        boring = self.auto_detect_boring_ranges(
            source,
            total_duration,
            silence_seconds=silence_seconds,
            freeze_seconds=freeze_seconds,
            black_seconds=black_seconds,
            noise_floor_db=noise_floor_db,
        )
        if not boring:
            return [
                {
                    "start": 0.0,
                    "end": round(total_duration, 3),
                    "kind": "keep",
                    "speed": 1.0,
                    "name": "Auto Keep 01",
                }
            ], []

        keep_ranges: list[tuple[float, float]] = []
        cursor = 0.0
        for region in boring:
            if region["start"] - cursor >= min_keep_seconds:
                keep_ranges.append((round(cursor, 3), round(region["start"], 3)))
            cursor = max(cursor, region["end"])
        if total_duration - cursor >= min_keep_seconds:
            keep_ranges.append((round(cursor, 3), round(total_duration, 3)))

        if action == "remove":
            segments = []
            for idx, (start, end) in enumerate(keep_ranges, start=1):
                segments.append(
                    {
                        "start": start,
                        "end": end,
                        "kind": "keep",
                        "speed": 1.0,
                        "name": f"Auto Keep {idx:02d}",
                    }
                )
            return segments, boring

        # action == speedup
        speed = max(1.5, min(float(speed_factor), 64.0))
        segments: list[dict] = []
        cursor = 0.0
        keep_idx = 1
        boring_idx = 1
        for region in boring:
            if region["start"] > cursor:
                segments.append(
                    {
                        "start": round(cursor, 3),
                        "end": round(region["start"], 3),
                        "kind": "keep",
                        "speed": 1.0,
                        "name": f"Keep {keep_idx:02d}",
                    }
                )
                keep_idx += 1
            segments.append(
                {
                    "start": round(region["start"], 3),
                    "end": round(region["end"], 3),
                    "kind": "boring",
                    "speed": speed,
                    "name": f"Fast Forward {boring_idx:02d}",
                }
            )
            boring_idx += 1
            cursor = region["end"]
        if cursor < total_duration:
            segments.append(
                {
                    "start": round(cursor, 3),
                    "end": round(total_duration, 3),
                    "kind": "keep",
                    "speed": 1.0,
                    "name": f"Keep {keep_idx:02d}",
                }
            )

        # Remove ultra-short fragments that are usually artifacts.
        segments = [
            s for s in segments
            if s["end"] - s["start"] >= 0.5
        ]
        return segments, boring

    def apply_retention_rules(
        self,
        clips: list,
        transition_min_clip_seconds: float = 20.0,
        apply_sfx: bool = True,
        apply_transitions: bool = True,
        imply_slowmo_for_short_keep: bool = False,
    ) -> dict:
        """
        Apply retention-oriented defaults on generated clips.
        Returns counters for UI reporting.
        """
        transitions = 0
        sfx = 0
        slowmo = 0

        if apply_transitions:
            for i, clip in enumerate(clips[:-1]):
                nxt = clips[i + 1]
                if clip.duration >= transition_min_clip_seconds and nxt.duration >= transition_min_clip_seconds:
                    if clip.speed <= 1.25 and nxt.speed <= 1.25:
                        clip.transition_out = "dissolve"
                        clip.transition_duration = 0.35
                        transitions += 1
                    else:
                        clip.transition_out = "none"

        if apply_sfx:
            for clip in clips:
                if clip.speed >= 2.0:
                    evt = {"name": "whoosh", "offset": 0.0, "volume": 0.65}
                    if evt not in clip.sfx_events:
                        clip.sfx_events.append(evt)
                        sfx += 1
                elif clip.transition_out == "none" and clip.duration >= 6.0:
                    evt = {"name": "boom", "offset": max(0.0, clip.duration - 0.12), "volume": 0.45}
                    if evt not in clip.sfx_events:
                        clip.sfx_events.append(evt)
                        sfx += 1

        if imply_slowmo_for_short_keep:
            for clip in clips:
                if clip.speed == 1.0 and 2.0 <= clip.duration <= 6.0:
                    clip.speed = 0.75
                    slowmo += 1

        return {"transitions": transitions, "sfx": sfx, "slowmo": slowmo}

    def generate_auto_captions_for_clip(
        self,
        source: Path,
        clip,
        min_speech_seconds: float = 0.8,
        font: str = "Bebas Neue",
        effect: str = "pop",
    ) -> list[dict]:
        """
        Generate editable caption placeholders from detected speech regions.
        Text is intentionally placeholder because full speech-to-text is not bundled.
        """
        from god_factory_editor.core.audio_enhancer import audio_enhancer

        regions = audio_enhancer.detect_speech_regions(
            source,
            clip.start_time,
            clip.duration,
            noise_floor_db=float(settings.get("automation_noise_floor_db", -40.0)),
            min_silence_s=0.2,
            voice_band_low_hz=float(settings.get("voice_band_low_hz", 180.0)),
            voice_band_high_hz=float(settings.get("voice_band_high_hz", 3400.0)),
            voice_sensitivity=float(settings.get("voice_sensitivity", 1.0)),
        )
        captions = []
        idx = 1
        for r in regions:
            if not r.is_speech or r.duration < min_speech_seconds:
                continue
            captions.append(
                {
                    "start": round(r.start, 3),
                    "end": round(r.end, 3),
                    "text": f"Edit caption {idx}",
                    "font": font,
                    "effect": effect,
                }
            )
            idx += 1
        return captions


# Module-level singleton
effects_engine = EffectsEngine()
