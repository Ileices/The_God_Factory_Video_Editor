"""
AudioEnhancer — dialogue detection and voice/audio enhancement pipeline.

Key problems solved:
1. Voice is quiet / game audio floods it  →  voice frequency boost + dynamic
   compression to raise the 300–3400 Hz voice band above game noise
2. Detecting when people are speaking    →  silence/energy detection via FFmpeg
3. Loudness normalization for consistent YouTube-level audio

Note: True speaker separation from mixed audio requires ML models (Demucs,
Spleeter) which are large downloads.  This module uses FFmpeg-only DSP filters
which give a significant improvement without any extra dependencies.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple

from god_factory_editor.utils.logger import log


# ── Audio filter presets ───────────────────────────────────────────────────────
AUDIO_PRESETS: list[dict] = [
    {
        "id": "none",
        "label": "No enhancement",
        "description": "Export audio exactly as recorded.",
        "voice_boost": 0.0,
        "game_duck": 0.0,
        "normalize": False,
        "denoise": False,
    },
    {
        "id": "voice_boost_light",
        "label": "Voice Boost — Light (+4 dB)",
        "description": (
            "Gently raises voice frequencies. Good when your mic is slightly low "
            "but game audio isn't too overwhelming."
        ),
        "voice_boost": 4.0,
        "game_duck": 0.0,
        "normalize": False,
        "denoise": False,
    },
    {
        "id": "voice_boost_strong",
        "label": "Voice Boost — Strong (+8 dB)",
        "description": (
            "Strong voice presence boost. Good for teammates whose mics are very "
            "quiet in the mix. Also applies dynamic compression to raise the "
            "quietest parts of speech."
        ),
        "voice_boost": 8.0,
        "game_duck": 3.0,
        "normalize": False,
        "denoise": False,
    },
    {
        "id": "game_duck",
        "label": "Duck Game Audio (keep voice)",
        "description": (
            "Cuts low-frequency game bass/rumble and reduces game-audio-dominant "
            "frequencies while preserving the 300 Hz–3.4 kHz voice band. "
            "Your own loud voice is unaffected."
        ),
        "voice_boost": 4.0,
        "game_duck": 6.0,
        "normalize": False,
        "denoise": False,
    },
    {
        "id": "clean_and_loud",
        "label": "Clean & Loud (normalize + denoise)",
        "description": (
            "Full cleanup: noise reduction, voice boost, and loudness normalization "
            "to -16 LUFS (YouTube standard). Best quality but slower to export."
        ),
        "voice_boost": 6.0,
        "game_duck": 4.0,
        "normalize": True,
        "denoise": True,
    },
    {
        "id": "normalize_only",
        "label": "Normalize Loudness only",
        "description": (
            "Adjusts overall loudness to EBU R128 / YouTube standard (-16 LUFS). "
            "Does not change the voice/game balance."
        ),
        "voice_boost": 0.0,
        "game_duck": 0.0,
        "normalize": True,
        "denoise": False,
    },
]

AUDIO_PRESET_MAP: dict[str, dict] = {p["id"]: p for p in AUDIO_PRESETS}


class DialogueRegion:
    """Represents a time range where speech/audio was detected."""

    def __init__(self, start: float, end: float, is_speech: bool):
        self.start = start
        self.end = end
        self.is_speech = is_speech

    @property
    def duration(self) -> float:
        return self.end - self.start

    def __repr__(self) -> str:
        kind = "SPEECH" if self.is_speech else "SILENT"
        return f"<{kind} {self.start:.2f}–{self.end:.2f}s>"


class AudioEnhancer:
    """
    Analyses audio to detect speech regions and builds FFmpeg audio filter
    strings for voice enhancement.
    """

    # ── Dialogue detection ────────────────────────────────────────────────────
    def detect_speech_regions(
        self,
        source: Path,
        start: float,
        duration: float,
        noise_floor_db: float = -38.0,
        min_silence_s: float = 0.25,
    ) -> List[DialogueRegion]:
        """
        Detect speech vs silent regions within a clip window.
        Returns a list of DialogueRegion objects in time order.

        Algorithm:
        - Run FFmpeg silencedetect on the clip window
        - The gaps between silent periods are audio regions (speech + game)
        - We then classify audio regions as "dialogue" or "game noise" based
          on their energy and position, helping the UI show safe cut points
        """
        from god_factory_editor.utils.ffmpeg_wrapper import ffmpeg as ff
        silences = ff.detect_silence(
            source, start, duration,
            noise_floor_db=noise_floor_db,
            min_duration=min_silence_s,
        )

        regions: List[DialogueRegion] = []
        prev_end = 0.0  # relative to clip start

        # Adjust silences to be relative to clip start
        rel_silences = [
            (max(0.0, s - start), max(0.0, e - start))
            for s, e in silences
        ]

        for s_start, s_end in rel_silences:
            if s_start > prev_end + 0.05:
                # Audio region before this silence
                regions.append(DialogueRegion(prev_end, s_start, is_speech=True))
            regions.append(DialogueRegion(s_start, s_end, is_speech=False))
            prev_end = s_end

        # Final audio region after last silence
        if prev_end < duration - 0.05:
            regions.append(DialogueRegion(prev_end, duration, is_speech=True))

        return regions

    def find_safe_cut_points(
        self,
        source: Path,
        start: float,
        end: float,
        margin: float = 0.3,
    ) -> List[float]:
        """
        Return timestamps (absolute, in source time) that are safe to cut at
        without interrupting dialogue. Safe = silent for at least `margin` seconds.
        """
        dur = end - start
        regions = self.detect_speech_regions(source, start, dur)
        safe: List[float] = []
        for r in regions:
            if not r.is_speech and r.duration >= margin:
                # Middle of the silent region is safest
                mid = start + r.start + r.duration / 2
                safe.append(round(mid, 3))
        return safe

    # ── Filter string builders ─────────────────────────────────────────────────
    def build_audio_filter(
        self,
        voice_boost_db: float = 0.0,
        game_duck_db: float = 0.0,
        normalize: bool = False,
        denoise: bool = False,
        speed: float = 1.0,
    ) -> Optional[str]:
        """
        Build an FFmpeg -af filter string for audio enhancement.
        Returns None if no filters needed.
        """
        parts: List[str] = []

        if denoise:
            # arnndn is the AI noise reduction filter — requires a model file.
            # We fall back to anlmdn (non-local means denoiser) which is built-in.
            parts.append("anlmdn=s=7:p=0.002:r=0.002:m=15")

        if game_duck_db > 0:
            # Remove low-frequency game rumble / bass impact
            parts.append(f"highpass=f=180")
            # Reduce the 80–200 Hz bass band (game cannon blasts etc.)
            parts.append(
                f"equalizer=f=120:width_type=h:width=120:g=-{game_duck_db:.1f}"
            )

        if voice_boost_db > 0:
            # Boost 300 Hz–3400 Hz (core human voice intelligibility range)
            parts.append(
                f"equalizer=f=1700:width_type=h:width=2400:g={voice_boost_db:.1f}"
            )
            # Dynamic compression: bring up quiet speech, limit loud bursts
            # Format: attacks=secs:decays=secs:points=dBin/dBout pairs
            parts.append(
                "compand="
                "attacks=0.02:decays=0.15:"
                "points=-90/-90 -60/-50 -35/-30 -12/-8 0/-3 20/0"
            )

        if normalize:
            # EBU R128 loudness normalization to -16 LUFS (YouTube target)
            parts.append("loudnorm=I=-16:TP=-1.5:LRA=11")

        if speed != 1.0:
            # Audio speed (atempo chains)
            from god_factory_editor.utils.ffmpeg_wrapper import _build_atempo_chain
            parts.extend(_build_atempo_chain(speed))

        if not parts:
            return None
        return ",".join(parts)

    def analyse_clip(
        self,
        source: Path,
        clip,  # Clip instance (avoid circular import)
    ) -> dict:
        """
        Run a quick analysis on a clip and return recommendations.
        Results can be shown in the UI to help the user choose settings.
        """
        from god_factory_editor.utils.ffmpeg_wrapper import ffmpeg as ff
        dur = clip.end_time - clip.start_time
        loudness = ff.detect_loudness(source, clip.start_time, min(dur, 30.0))

        recommendations: list[str] = []
        preset_id = "none"

        lufs = loudness.get("integrated_lufs")
        if lufs is not None:
            if lufs < -23:
                recommendations.append(
                    f"Audio is quiet ({lufs:.1f} LUFS). "
                    "Consider normalizing or boosting voice."
                )
                preset_id = "voice_boost_light"
            elif lufs > -10:
                recommendations.append(
                    f"Audio is very loud ({lufs:.1f} LUFS). "
                    "Normalization recommended."
                )
                preset_id = "normalize_only"
            else:
                recommendations.append(
                    f"Audio level looks fine ({lufs:.1f} LUFS)."
                )

        # Check speech ratio
        regions = self.detect_speech_regions(source, clip.start_time, dur)
        speech_total = sum(r.duration for r in regions if r.is_speech)
        speech_pct = speech_total / dur * 100 if dur > 0 else 0
        if speech_pct > 70:
            recommendations.append(
                f"High dialogue content ({speech_pct:.0f}% speech). "
                "Voice Boost is recommended."
            )
            if preset_id == "none":
                preset_id = "voice_boost_strong"
        elif speech_pct < 20:
            recommendations.append(
                f"Mostly game audio ({100-speech_pct:.0f}%). "
                "Normalization-only recommended."
            )

        return {
            "lufs": lufs,
            "speech_pct": speech_pct,
            "recommendations": recommendations,
            "suggested_preset": preset_id,
        }


# Module-level singleton
audio_enhancer = AudioEnhancer()
