"""
ExportEngine — batch export of clips using FFmpeg.
Runs in a background QThread so the UI stays responsive.
Supports: stream-copy fast export, re-encode with speed/audio effects,
          multi-clip concat with xfade transitions.
"""

from __future__ import annotations
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QThread, Signal

from god_factory_editor.models.clip import Clip
from god_factory_editor.utils.ffmpeg_wrapper import FFmpegWrapper, ffmpeg as _default_ff
from god_factory_editor.utils.file_utils import (
    sanitise_filename, ensure_unique_path, free_space_bytes,
    estimate_export_size, human_bytes,
)
from god_factory_editor.utils.logger import log
from god_factory_editor.config import EXPORT_PRESETS, settings


class ExportEngine(QThread):
    """
    Signals
    -------
    progress(current, total)      — how many clips done
    clip_started(name, index)     — about to export this clip
    clip_done(name, path)         — clip exported successfully
    clip_failed(name, reason)     — clip failed
    all_done(results)             — {'success': [...], 'failed': [...]}
    status_message(text)          — one-liner status for the UI
    """

    progress = Signal(int, int)
    clip_started = Signal(str, int)
    clip_done = Signal(str, Path)
    clip_failed = Signal(str, str)
    all_done = Signal(dict)
    status_message = Signal(str)

    def __init__(self, ff: Optional[FFmpegWrapper] = None, parent=None):
        super().__init__(parent)
        self._ff = ff or _default_ff
        self._queue: List[Clip] = []
        self._source: Optional[Path] = None
        self._output_dir: Optional[Path] = None
        self._preset_key: str = "fast"
        self._export_as_single: bool = False
        self._abort = False

    # ── Configuration ─────────────────────────────────────────────────────────
    def configure(self,
                  source: Path,
                  clips: List[Clip],
                  output_dir: Path,
                  preset_key: str = "fast",
                  export_as_single: bool = False):
        """
        export_as_single: if True, all clips are concatenated with transitions
        into one output file instead of individual files.
        """
        self._source = source
        self._queue = list(clips)
        self._output_dir = output_dir
        self._preset_key = preset_key
        self._export_as_single = export_as_single
        self._abort = False

    # ── Pre-flight validation ─────────────────────────────────────────────────
    def validate(self) -> tuple[bool, str]:
        """Call before starting. Returns (ok, error_message)."""
        if not self._source or not self._source.exists():
            return False, "Source video file not found."
        if not self._queue:
            return False, "No clips selected for export."
        if not self._output_dir:
            return False, "No output folder selected."

        # Disk space estimate
        total_duration = sum(c.duration for c in self._queue)
        bitrate = 50_000_000  # conservative 50 Mbps for 4K
        estimated_bytes = estimate_export_size(total_duration, bitrate)
        free = free_space_bytes(self._output_dir)
        if estimated_bytes > 0 and free > 0 and free < estimated_bytes * 1.5:
            return (
                False,
                f"Not enough disk space.\n"
                f"Need approx {human_bytes(estimated_bytes)} free "
                f"(have {human_bytes(free)})."
            )
        return True, ""

    def cancel(self):
        self._abort = True

    # ── Thread body ───────────────────────────────────────────────────────────
    def run(self):
        self._output_dir.mkdir(parents=True, exist_ok=True)
        total = len(self._queue)
        success_paths: List[Path] = []
        failed_names: List[str] = []
        preset = EXPORT_PRESETS.get(self._preset_key, EXPORT_PRESETS["fast"])

        if self._export_as_single and total > 1:
            self._run_concat_export(preset, success_paths, failed_names)
        else:
            self._run_individual_export(preset, success_paths, failed_names)

        results = {"success": success_paths, "failed": failed_names}
        self.all_done.emit(results)
        self.status_message.emit(
            f"Done: {len(success_paths)} exported, {len(failed_names)} failed."
        )

    def _run_individual_export(self, preset: dict,
                                success_paths: List[Path],
                                failed_names: List[str]):
        total = len(self._queue)
        for i, clip in enumerate(self._queue):
            if self._abort:
                self.status_message.emit("Export cancelled.")
                break

            name = clip.name or f"clip_{i+1:03d}"
            self.clip_started.emit(name, i)
            self.status_message.emit(f"Exporting {i+1}/{total}: {name}")

            safe_name = sanitise_filename(name)
            out_path = ensure_unique_path(self._output_dir / f"{safe_name}.mp4")

            try:
                ok = self._export_one(clip, out_path, preset)
            except Exception as exc:
                log.error(f"Export exception for '{name}': {exc}")
                ok = False

            if ok:
                clip.export_status = "exported"
                clip.export_path = out_path
                success_paths.append(out_path)
                self.clip_done.emit(name, out_path)
                log.info(f"Exported: {out_path.name}")
            else:
                clip.export_status = "failed"
                failed_names.append(name)
                self.clip_failed.emit(name, "FFmpeg returned an error. Check logs.")
                log.warning(f"Export failed: {name}")

            self.progress.emit(i + 1, total)

    def _run_concat_export(self, preset: dict,
                            success_paths: List[Path],
                            failed_names: List[str]):
        """
        Export all clips into one file with xfade transitions between them.
        Each clip is first exported to a temp file with its effects applied,
        then all temps are concatenated with the xfade filter.
        """
        import os
        total = len(self._queue)
        tmp_dir = Path(tempfile.mkdtemp(prefix="gfve_concat_"))
        segments: List[dict] = []
        all_ok = True

        self.status_message.emit("Preparing clips with effects…")

        for i, clip in enumerate(self._queue):
            if self._abort:
                break
            name = clip.name or f"clip_{i+1:03d}"
            self.clip_started.emit(name, i)
            self.status_message.emit(f"Processing {i+1}/{total}: {name}")

            tmp_out = tmp_dir / f"seg_{i:04d}.mp4"
            try:
                ok = self._export_one(clip, tmp_out, preset)
            except Exception as exc:
                log.error(f"Segment export error '{name}': {exc}")
                ok = False

            if ok and tmp_out.exists():
                segments.append({
                    "path": tmp_out,
                    "transition": clip.transition_out,
                    "transition_duration": clip.transition_duration,
                })
            else:
                failed_names.append(name)
                all_ok = False
                self.clip_failed.emit(name, "Failed to prepare segment.")

            self.progress.emit(i + 1, total + 1)

        if segments:
            self.status_message.emit("Concatenating with transitions…")
            out_name = sanitise_filename(
                self._queue[0].name or "compilation"
            ) + "_compilation.mp4"
            out_path = ensure_unique_path(self._output_dir / out_name)
            crf = preset.get("crf", 18)
            ok = self._ff.export_clips_concat(segments, out_path, crf=crf)
            if ok:
                success_paths.append(out_path)
                self.clip_done.emit(out_name, out_path)
            else:
                failed_names.append("compilation")
                self.clip_failed.emit("compilation", "Concat/transition export failed.")

        # Cleanup temp files
        for seg in segments:
            try:
                seg["path"].unlink(missing_ok=True)
            except Exception:
                pass
        try:
            tmp_dir.rmdir()
        except Exception:
            pass

        self.progress.emit(total + 1, total + 1)

    # ── Internal export dispatch ──────────────────────────────────────────────
    def _export_one(self, clip: Clip, output: Path, preset: dict) -> bool:
        """
        Dispatch to fast copy OR effects-aware encode depending on what the
        clip requires.
        """
        needs_effects = (
            abs(clip.speed - 1.0) > 0.001
            or clip.audio_voice_boost > 0
            or clip.audio_game_duck > 0
            or clip.audio_normalize
            or clip.audio_denoise
            or abs(clip.picture_brightness) > 0.001
            or abs(clip.picture_contrast - 1.0) > 0.001
            or abs(clip.picture_saturation - 1.0) > 0.001
            or abs(clip.picture_gamma - 1.0) > 0.001
            or abs(clip.picture_sharpen) > 0.001
        )

        video_codec = preset.get("video_codec", "copy")
        duration = clip.duration

        if needs_effects or video_codec != "copy":
            # Always re-encode when effects are active
            result = self._ff.export_clip_with_effects(
                source=self._source,
                start=clip.start_time,
                duration=duration,
                output=output,
                speed=clip.speed,
                voice_boost_db=clip.audio_voice_boost,
                game_duck_db=clip.audio_game_duck,
                normalize=clip.audio_normalize,
                denoise=clip.audio_denoise,
                picture_brightness=clip.picture_brightness,
                picture_contrast=clip.picture_contrast,
                picture_saturation=clip.picture_saturation,
                picture_gamma=clip.picture_gamma,
                picture_sharpen=clip.picture_sharpen,
                crf=preset.get("crf", 18),
                resolution=preset.get("resolution"),
            )
        else:
            result = self._ff.export_clip_fast(
                self._source, clip.start_time, duration, output
            )

        # Apply SFX events if any (mix in sound effects)
        if result and clip.sfx_events:
            result = self._apply_sfx(clip, output)

        return result

    def _apply_sfx(self, clip: Clip, video_path: Path) -> bool:
        """Overlay SFX audio events onto an already-exported clip file."""
        from god_factory_editor.core.effects_engine import effects_engine
        import shutil

        if not clip.sfx_events:
            return True

        # Build FFmpeg amix inputs and filter chain
        inputs = [self._ff.ffmpeg, "-y", "-i", str(video_path)]
        af_inputs: List[str] = []

        info = self._ff.get_video_info(video_path) or {}
        has_main_audio = any(
            s.get("codec_type") == "audio"
            for s in info.get("streams", [])
        )

        valid_sfx = []
        for evt in clip.sfx_events:
            sfx_path = effects_engine.ensure_sfx(evt.get("name", ""))
            if sfx_path and sfx_path.exists():
                inputs += ["-i", str(sfx_path)]
                idx = len(valid_sfx) + 1  # 0 = main video
                offset = evt.get("offset", 0.0)
                vol = evt.get("volume", 0.7)
                af_inputs.append(
                    f"[{idx}:a]adelay={int(offset*1000)}|{int(offset*1000)},"
                    f"volume={vol:.2f}[sfx{idx}]"
                )
                valid_sfx.append(f"[sfx{idx}]")

        if not valid_sfx:
            return True

        # Mix all sfx streams with main audio (if present)
        mix_inputs = ("[0:a]" if has_main_audio else "") + "".join(valid_sfx)
        input_count = (1 if has_main_audio else 0) + len(valid_sfx)
        filter_complex = (
            "; ".join(af_inputs) + "; "
            f"{mix_inputs}amix=inputs={input_count}:duration=first[aout]"
        )

        tmp = video_path.with_suffix(".sfx_tmp.mp4")
        args = (
            inputs
            + [
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                str(tmp),
            ]
        )
        ok, _, _ = self._ff.run(args, timeout=600)
        if ok and tmp.exists():
            shutil.move(str(tmp), str(video_path))
            log.debug(
                f"Applied {len(valid_sfx)} SFX event(s) to {video_path.name} "
                f"(main_audio={has_main_audio})"
            )
            return True
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False
