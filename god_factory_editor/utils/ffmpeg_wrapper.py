"""
FFmpeg wrapper — all subprocess calls to ffmpeg / ffprobe.
Provides caching for video info queries.
"""

from __future__ import annotations
import json
import re
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from god_factory_editor.config import FFMPEG_EXE, FFPROBE_EXE
from god_factory_editor.utils.logger import log


_INFO_CACHE: Dict[str, dict] = {}
_CACHE_LOCK = threading.Lock()


class FFmpegError(RuntimeError):
    pass


class FFmpegWrapper:
    """Thin wrapper around ffmpeg/ffprobe subprocesses."""

    # All candidates in preference order. Probed at runtime to skip broken ones.
    _ENCODER_CANDIDATES = ["h264_nvenc", "h264_qsv", "h264_amf", "h264_mf", "libx264"]

    def __init__(self,
                 ffmpeg_path: Path = FFMPEG_EXE,
                 ffprobe_path: Path = FFPROBE_EXE):
        self.ffmpeg = str(ffmpeg_path)
        self.ffprobe = str(ffprobe_path)
        self.last_error: str = ""
        self._preferred_h264_encoder: Optional[str] = None
        self._preferred_hevc_encoder: Optional[str] = None
        self._available_h264_encoders: Optional[List[str]] = None
        self._working_h264_encoders: Optional[List[str]] = None  # live-tested

    # ── Low-level runner ──────────────────────────────────────────────────────
    def run(self,
            args: List[str],
            timeout: int = 300,
            stdin=None) -> Tuple[bool, str, str]:
        """
        Execute a command.
        Returns (success, stdout, stderr).
        """
        log.debug(f"FFmpeg cmd: {' '.join(args)}")
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=stdin,
            )
            success = result.returncode == 0
            if not success:
                self.last_error = (result.stderr or "")[-1500:]
                log.warning(f"FFmpeg exit {result.returncode}: {result.stderr[-500:]}")
            else:
                self.last_error = ""
            return success, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            log.error(f"FFmpeg timed out after {timeout}s")
            self.last_error = "Process timed out"
            return False, "", "Process timed out"
        except FileNotFoundError:
            log.error(f"FFmpeg not found at: {self.ffmpeg}")
            self.last_error = f"FFmpeg executable not found: {self.ffmpeg}"
            return False, "", "FFmpeg executable not found"
        except Exception as exc:
            log.error(f"FFmpeg run error: {exc}")
            self.last_error = str(exc)
            return False, "", str(exc)

    # ── Probe ─────────────────────────────────────────────────────────────────
    def get_video_info(self, path: Path) -> Optional[dict]:
        """
        Return ffprobe JSON for a video file.
        Results are cached per file path.
        """
        key = str(path)
        with _CACHE_LOCK:
            if key in _INFO_CACHE:
                return _INFO_CACHE[key]

        args = [
            self.ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        ok, stdout, stderr = self.run(args, timeout=30)
        if not ok or not stdout.strip():
            return None

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return None

        with _CACHE_LOCK:
            _INFO_CACHE[key] = data
        return data

    # ── Export ────────────────────────────────────────────────────────────────
    def export_clip_fast(self,
                         source: Path,
                         start: float,
                         duration: float,
                         output: Path,
                         on_progress=None) -> bool:
        """
        Stream-copy export (near-instant, no re-encode).
        on_progress(percent: float) is called periodically if provided.
        """
        args = [
            self.ffmpeg, "-y",
        ] + self.hardware_decode_args() + [
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            str(output),
        ]
        ok, _, stderr = self.run(args, timeout=120)
        return ok

    def export_clip_accurate(self,
                             source: Path,
                             start: float,
                             duration: float,
                             output: Path,
                             crf: int = 18,
                             speed_preset: str = "veryfast",
                             resolution: Optional[List[int]] = None) -> bool:
        """
        Re-encode export — frame-accurate cuts.
        """
        def _build_args(vcodec: str, use_hwdecode: bool) -> List[str]:
            args = [self.ffmpeg, "-y"]

            if use_hwdecode and vcodec != "libx264":
                # Full GPU pipeline: GPU decode → optional GPU scale → GPU encode
                args += self._gpu_full_pipeline_decode_args(vcodec)
                args += ["-ss", str(start), "-i", str(source), "-t", str(duration)]
                if resolution:
                    gpu_sf = self._gpu_scale_filter(vcodec, resolution[0], resolution[1])
                    if gpu_sf:
                        args += ["-vf", gpu_sf]
                    else:
                        fmt = self._cpu_format_for_encoder(vcodec)
                        vf = f"scale={resolution[0]}:{resolution[1]}:flags=lanczos"
                        if fmt:
                            vf += f",format={fmt}"
                        args += ["-vf", vf]
            else:
                # CPU decode → CPU scale → format → encode
                args += ["-ss", str(start), "-i", str(source), "-t", str(duration)]
                vf_parts = []
                if resolution:
                    vf_parts.append(f"scale={resolution[0]}:{resolution[1]}:flags=lanczos")
                fmt = self._cpu_format_for_encoder(vcodec)
                if fmt:
                    vf_parts.append(f"format={fmt}")
                if vf_parts:
                    args += ["-vf", ",".join(vf_parts)]

            args += ["-c:a", "aac", "-b:a", "192k", "-c:v", vcodec, "-movflags", "+faststart"]
            args += self.hardware_encode_quality_args(vcodec, crf=crf, preset=speed_preset)
            args.append(str(output))
            return args

        return self._run_h264_with_fallback(
            build_args=_build_args,
            timeout=3600,
            context=f"accurate export {source.name}",
        )

    # ── Proxy ─────────────────────────────────────────────────────────────────
    def generate_proxy(self,
                       source: Path,
                       output: Path,
                       width: int = 854,
                       height: int = 480) -> bool:
        """Create a low-resolution preview copy for smooth scrubbing."""
        def _build_args(vcodec: str, use_hwdecode: bool) -> List[str]:
            args = [self.ffmpeg, "-y"]
            if use_hwdecode and vcodec != "libx264":
                # Full GPU pipeline: GPU decode → GPU scale → GPU encode
                args += self._gpu_full_pipeline_decode_args(vcodec)
                args += ["-i", str(source)]
                gpu_sf = self._gpu_scale_filter(vcodec, width, height)
                vf = gpu_sf or f"scale={width}:{height}:flags=lanczos"
            else:
                # CPU decode → CPU scale → format convert → encode
                args += ["-i", str(source)]
                vf_parts = [f"scale={width}:{height}:flags=lanczos"]
                fmt = self._cpu_format_for_encoder(vcodec)
                if fmt:
                    vf_parts.append(f"format={fmt}")
                vf = ",".join(vf_parts)
            args += ["-vf", vf, "-an", "-c:v", vcodec]
            args += self.hardware_encode_quality_args(vcodec, crf=28, preset="p1")
            args += [str(output)]
            return args

        return self._run_h264_with_fallback(
            build_args=_build_args,
            timeout=7200,
            context=f"proxy generation {source.name}",
        )

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    def extract_frame(self,
                      source: Path,
                      time_seconds: float,
                      output: Path,
                      width: int = 320,
                      height: int = 180) -> bool:
        """Extract a single frame as an image file."""
        # Try with GPU decode first (faster seek), fall back to CPU
        for gpu_args in (
            ["-hwaccel", "cuda"],
            ["-hwaccel", "d3d11va"],
            [],
        ):
            args = [self.ffmpeg, "-y"] + gpu_args + [
                "-ss", str(time_seconds),
                "-i", str(source),
                "-vframes", "1",
                "-vf", f"scale={width}:{height}:flags=lanczos",
                str(output),
            ]
            ok, _, _ = self.run(args, timeout=30)
            if ok:
                return True
        return False

    # ── Speed-aware export ────────────────────────────────────────────────────
    def export_clip_with_effects(self,
                                 source: Path,
                                 start: float,
                                 duration: float,
                                 output: Path,
                                 speed: float = 1.0,
                                 voice_boost_db: float = 0.0,
                                 game_duck_db: float = 0.0,
                                 normalize: bool = False,
                                 denoise: bool = False,
                                 picture_brightness: float = 0.0,
                                 picture_contrast: float = 1.0,
                                 picture_saturation: float = 1.0,
                                 picture_gamma: float = 1.0,
                                 picture_sharpen: float = 0.0,
                                 crf: int = 18,
                                 resolution: Optional[List[int]] = None) -> bool:
        """
        Re-encode a clip with optional speed change, audio filters, and resolution.
        Must be used (instead of fast copy) whenever any effect is active.
        """
        # ── Video filter chain ────────────────────────────────────────────────
        vf_parts: List[str] = []
        if resolution:
            vf_parts.append(
                f"scale={resolution[0]}:{resolution[1]}:flags=lanczos"
            )
        if (
            abs(picture_brightness) > 0.001
            or abs(picture_contrast - 1.0) > 0.001
            or abs(picture_saturation - 1.0) > 0.001
            or abs(picture_gamma - 1.0) > 0.001
        ):
            vf_parts.append(
                "eq="
                f"brightness={picture_brightness:.3f}:"
                f"contrast={picture_contrast:.3f}:"
                f"saturation={picture_saturation:.3f}:"
                f"gamma={picture_gamma:.3f}"
            )
        if picture_sharpen > 0.001:
            amount = max(0.0, min(2.0, picture_sharpen))
            vf_parts.append(
                f"unsharp=5:5:{amount:.3f}:5:5:0.0"
            )
        if speed != 1.0:
            vf_parts.append(f"setpts={1.0/speed:.6f}*PTS")
        vf = ",".join(vf_parts) if vf_parts else None

        # ── Audio filter chain ────────────────────────────────────────────────
        af_parts: List[str] = []
        if denoise:
            # arnndn is built into recent FFmpeg; gracefully skip if unavailable
            af_parts.append("arnndn=m=cb.rnnn")
        if game_duck_db > 0:
            # Cut low-freq game rumble (bass below ~200 Hz)
            af_parts.append(f"highpass=f=180")
            af_parts.append(f"equalizer=f=100:width_type=h:width=150:g=-{game_duck_db:.1f}")
        if voice_boost_db > 0:
            # Boost the human-voice frequency band (300 Hz – 3.4 kHz)
            af_parts.append(
                f"equalizer=f=1800:width_type=h:width=2400:g={voice_boost_db:.1f}"
            )
            # Dynamic compression to raise quiet voices
            af_parts.append("compand=attacks=0.01:decays=0.1:points=-90/-90 -45/-45 -12/-6 0/-3 20/0")
        if normalize:
            af_parts.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        if speed != 1.0:
            af_parts += _build_atempo_chain(speed)
        af = ",".join(af_parts) if af_parts else None

        def _build_args(vcodec: str, use_hwdecode: bool) -> List[str]:
            # SW filters (eq, unsharp, setpts, etc.) require CPU frames.
            # Always: CPU decode → SW filters → format convert → GPU (or SW) encode.
            # use_hwdecode=True here means "first attempt" (same pipeline since SW filters force CPU path).
            args = [self.ffmpeg, "-y"]
            args += [
                "-ss", str(start),
                "-i", str(source),
                "-t", str(duration),
            ]

            # Append pixel format conversion to vf chain for GPU encoders
            vf_final = vf
            if vcodec != "libx264":
                fmt = self._cpu_format_for_encoder(vcodec)
                if fmt:
                    vf_final = f"{vf},format={fmt}" if vf else f"format={fmt}"

            args += [
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                "-c:v", vcodec,
            ]
            args += self.hardware_encode_quality_args(vcodec, crf=crf, preset="p4")
            if vf_final:
                args += ["-vf", vf_final]
            if af:
                args += ["-af", af]
            args.append(str(output))
            return args

        return self._run_h264_with_fallback(
            build_args=_build_args,
            timeout=3600,
            context=f"effects export {source.name}",
        )

    # ── Concat with xfade transitions ─────────────────────────────────────────
    def export_clips_concat(self,
                            segments: List[dict],
                            output: Path,
                            crf: int = 18) -> bool:
        """
        Concatenate pre-exported segments with optional xfade transitions.

        segments: [
          {
            "path": Path,                  # already-exported temp clip
            "transition": "dissolve",      # xfade name, or "none"/"fade"/"fadeblack"
            "transition_duration": 0.5,    # seconds
          },
          ...
        ]
        Builds a filtergraph using xfade + acrossfade for each boundary.
        """
        if not segments:
            return False
        if len(segments) == 1:
            import shutil
            shutil.copy2(segments[0]["path"], output)
            return True

        # Build complex filter: each clip input → xfade chain
        inputs = []
        for seg in segments:
            inputs += self.hardware_decode_args() + ["-i", str(seg["path"])]

        # ── Determine cumulative durations for xfade offsets ─────────────────
        durations = []
        has_audio_flags = []
        for seg in segments:
            info = self.get_video_info(seg["path"])
            dur = 0.0
            has_audio = False
            if info:
                try:
                    dur = float(info["format"]["duration"])
                except Exception:
                    pass
                has_audio = any(
                    s.get("codec_type") == "audio"
                    for s in info.get("streams", [])
                )
            durations.append(dur)
            has_audio_flags.append(has_audio)

        can_xfade_audio = all(has_audio_flags)
        if not can_xfade_audio:
            log.warning(
                "Concat audio crossfade disabled: one or more segments have no audio stream."
            )

        # Build the filter graph
        vf_parts: List[str] = []
        af_parts: List[str] = []
        v_label = "[0:v]"
        a_label = "[0:a]"

        cumulative = 0.0
        for i in range(len(segments) - 1):
            td = segments[i].get("transition_duration", 0.5)
            tname = segments[i].get("transition", "none")
            if tname in ("none", ""):
                tname = "fade"  # default to fade if unspecified

            cumulative += durations[i] - td
            v_out = f"[v{i+1}]"
            a_out = f"[a{i+1}]"

            vf_parts.append(
                f"{v_label}[{i+1}:v]xfade="
                f"transition={tname}:duration={td}:offset={cumulative:.3f}"
                f"{v_out}"
            )
            if can_xfade_audio:
                af_parts.append(
                    f"{a_label}[{i+1}:a]acrossfade=d={td}{a_out}"
                )
            v_label = v_out
            if can_xfade_audio:
                a_label = a_out

        filter_parts = vf_parts + af_parts
        filter_complex = "; ".join(filter_parts)
        out_v = v_label
        out_a = a_label

        def _build_args(vcodec: str, use_hwdecode: bool) -> List[str]:
            # xfade is a software filter — always CPU filter path, GPU encode only.
            concat_inputs: List[str] = []
            for seg in segments:
                concat_inputs += ["-i", str(seg["path"])]

            # Append format filter to the last output label so GPU encoders get correct pixel format
            fmt = self._cpu_format_for_encoder(vcodec)
            if fmt:
                final_v = f"[vfmt]"
                fc = filter_complex + f"; {out_v}format={fmt}{final_v}"
                map_v = final_v
            else:
                fc = filter_complex
                map_v = out_v

            args = [self.ffmpeg, "-y"] + concat_inputs + [
                "-filter_complex", fc,
                "-map", map_v,
                "-c:v", vcodec,
            ]
            args += self.hardware_encode_quality_args(vcodec, crf=crf, preset="p4")
            if can_xfade_audio:
                args += [
                    "-map", out_a,
                    "-c:a", "aac",
                    "-b:a", "192k",
                ]
            else:
                args += ["-an"]
            args += ["-movflags", "+faststart", str(output)]
            return args

        return self._run_h264_with_fallback(
            build_args=_build_args,
            timeout=7200,
            context="concat export",
        )

    # ── Silence / loudness analysis ───────────────────────────────────────────
    def detect_silence(self,
                       source: Path,
                       start: float,
                       duration: float,
                       noise_floor_db: float = -40.0,
                       min_duration: float = 0.3) -> List[Tuple[float, float]]:
        """
        Return list of (start, end) SILENT regions within the clip window.
        Inverse of this = speech/game-audio segments.
        """
        args = [
            self.ffmpeg,
        ] + self.hardware_decode_args() + [
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-af", (
                f"silencedetect=noise={noise_floor_db}dB"
                f":duration={min_duration}"
            ),
            "-f", "null", "-",
        ]
        _, _, stderr = self.run(args, timeout=120)

        silences: List[Tuple[float, float]] = []
        s_start: Optional[float] = None
        for line in stderr.splitlines():
            if "silence_start" in line:
                try:
                    s_start = float(line.split("silence_start:")[-1].strip())
                except ValueError:
                    pass
            elif "silence_end" in line and s_start is not None:
                try:
                    s_end = float(line.split("silence_end:")[-1].split("|")[0].strip())
                    silences.append((s_start, s_end))
                    s_start = None
                except ValueError:
                    pass
        return silences

    def detect_loudness(self,
                        source: Path,
                        start: float,
                        duration: float) -> dict:
        """
        Run ebur128 loudness scan on a clip section.
        Returns dict with integrated_lufs, true_peak_dbtp, lra keys.
        """
        args = [
            self.ffmpeg,
        ] + self.hardware_decode_args() + [
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-af", "ebur128=peak=true",
            "-f", "null", "-",
        ]
        _, _, stderr = self.run(args, timeout=120)

        result = {"integrated_lufs": None, "true_peak_dbtp": None, "lra": None}
        for line in stderr.splitlines():
            if "Integrated loudness" in line and "I:" in line:
                try:
                    result["integrated_lufs"] = float(
                        line.split("I:")[-1].split("LUFS")[0].strip()
                    )
                except ValueError:
                    pass
            if "LRA:" in line and "LRA:" in line:
                try:
                    result["lra"] = float(
                        line.split("LRA:")[-1].split("LU")[0].strip()
                    )
                except ValueError:
                    pass
            if "True peak" in line and "Peak:" in line:
                try:
                    result["true_peak_dbtp"] = float(
                        line.split("Peak:")[-1].split("dBTP")[0].strip()
                    )
                except ValueError:
                    pass
        return result

    def detect_black(self,
                     source: Path,
                     start: float,
                     duration: float,
                     min_duration: float = 1.5,
                     pixel_threshold: float = 0.10,
                     picture_threshold: float = 0.98) -> List[Tuple[float, float]]:
        """Return black-screen regions within the clip window."""
        args = [
            self.ffmpeg,
        ] + self.hardware_decode_args() + [
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-vf",
            (
                f"blackdetect=d={min_duration}:"
                f"pix_th={pixel_threshold}:pic_th={picture_threshold}"
            ),
            "-an",
            "-f", "null", "-",
        ]
        _, _, stderr = self.run(args, timeout=180)

        black_ranges: List[Tuple[float, float]] = []
        black_start: Optional[float] = None
        for line in stderr.splitlines():
            if "black_start:" in line:
                try:
                    black_start = float(line.split("black_start:")[-1].split()[0].strip())
                except ValueError:
                    pass
            if "black_end:" in line and black_start is not None:
                try:
                    black_end = float(line.split("black_end:")[-1].split()[0].strip())
                    black_ranges.append((black_start, black_end))
                    black_start = None
                except ValueError:
                    pass
        return black_ranges

    def detect_freeze(self,
                      source: Path,
                      start: float,
                      duration: float,
                      min_duration: float = 2.0,
                      noise: float = 0.001) -> List[Tuple[float, float]]:
        """Return freeze-frame / no-motion regions within the clip window."""
        args = [
            self.ffmpeg,
        ] + self.hardware_decode_args() + [
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-vf", f"freezedetect=n={noise}:d={min_duration}",
            "-an",
            "-f", "null", "-",
        ]
        _, _, stderr = self.run(args, timeout=180)

        freeze_ranges: List[Tuple[float, float]] = []
        freeze_start: Optional[float] = None
        for line in stderr.splitlines():
            if "freeze_start:" in line:
                try:
                    freeze_start = float(line.split("freeze_start:")[-1].split()[0].strip())
                except ValueError:
                    pass
            if "freeze_end:" in line and freeze_start is not None:
                try:
                    freeze_end = float(line.split("freeze_end:")[-1].split()[0].strip())
                    freeze_ranges.append((freeze_start, freeze_end))
                    freeze_start = None
                except ValueError:
                    pass
        return freeze_ranges

    def detect_boring_combined(
        self,
        source: Path,
        start: float,
        duration: float,
        *,
        noise_floor_db: float = -38.0,
        silence_min: float = 10.0,
        freeze_min: float = 5.0,
        freeze_noise: float = 0.001,
        black_min: float = 1.5,
        black_pix_th: float = 0.10,
        black_pic_th: float = 0.98,
    ) -> tuple:
        """
        Single-pass combined detection: silence + freeze + black in one ffmpeg run.
        Returns (silences, freezes, blacks) — each a List[Tuple[float, float]].

        For an 8.5h VOD this is 3× faster than running separate passes because
        the video/audio only needs to be decoded once.  CPU handles decode,
        GPU hwaccel assists the demux/decode stage (-hwaccel auto).
        """
        # We need to split the video stream to run both freezedetect and blackdetect.
        # Audio stream gets silencedetect applied directly.
        fc = (
            f"[0:v]split=2[_vf][_vb];"
            f"[_vf]freezedetect=n={freeze_noise}:d={freeze_min}[vfreeze];"
            f"[_vb]blackdetect=d={black_min}:pix_th={black_pix_th}:pic_th={black_pic_th}[vblack];"
            f"[0:a]silencedetect=noise={noise_floor_db}dB:duration={silence_min}[asilent]"
        )
        args = (
            [self.ffmpeg]
            + self.hardware_decode_args()
            + ["-ss", str(start), "-i", str(source), "-t", str(duration)]
            + ["-filter_complex", fc]
            + ["-map", "[vfreeze]", "-map", "[vblack]", "-map", "[asilent]"]
            + ["-f", "null", "-"]
        )
        # timeout: allow ~1× realtime for long videos
        timeout = max(300, int(duration) + 120)
        _, _, stderr = self.run(args, timeout=timeout)

        silences: List[Tuple[float, float]] = []
        s_start: Optional[float] = None
        freezes: List[Tuple[float, float]] = []
        fr_start: Optional[float] = None
        blacks: List[Tuple[float, float]] = []
        bl_start: Optional[float] = None

        for line in stderr.splitlines():
            # silence
            if "silence_start:" in line:
                try:
                    s_start = float(line.split("silence_start:")[-1].strip())
                except ValueError:
                    pass
            elif "silence_end:" in line and s_start is not None:
                try:
                    s_end = float(line.split("silence_end:")[-1].split("|")[0].strip())
                    silences.append((s_start, s_end))
                    s_start = None
                except ValueError:
                    pass
            # freeze
            elif "freeze_start:" in line:
                try:
                    fr_start = float(line.split("freeze_start:")[-1].split()[0].strip())
                except ValueError:
                    pass
            elif "freeze_end:" in line and fr_start is not None:
                try:
                    fr_end = float(line.split("freeze_end:")[-1].split()[0].strip())
                    freezes.append((fr_start, fr_end))
                    fr_start = None
                except ValueError:
                    pass
            # black
            elif "black_start:" in line:
                try:
                    bl_start = float(line.split("black_start:")[-1].split()[0].strip())
                except ValueError:
                    pass
            elif "black_end:" in line and bl_start is not None:
                try:
                    bl_end = float(line.split("black_end:")[-1].split()[0].strip())
                    blacks.append((bl_start, bl_end))
                    bl_start = None
                except ValueError:
                    pass

        return silences, freezes, blacks

    # ── Availability check ────────────────────────────────────────────────────
    def _scan_list_output(self, args: List[str], kind: str) -> List[str]:
        """Parse ffmpeg list-style outputs (encoders/filters/protocols/etc)."""
        ok, stdout, _ = self.run([self.ffmpeg, "-hide_banner", *args], timeout=30)
        if not ok:
            return []

        names: List[str] = []
        for raw in stdout.splitlines():
            line = raw.rstrip()
            if not line or line.startswith(" ") is False:
                continue
            if line.strip().startswith("="):
                continue

            parts = line.split()
            if not parts:
                continue

            # Most ffmpeg list tables are: <flags> <name> <description...>
            # Some are: <name>
            token = parts[1] if len(parts) > 1 and re.fullmatch(r"[A-Z\.]{2,8}|[D\.EASVIFT]{2,8}", parts[0]) else parts[0]
            token = token.strip()
            if token and re.match(r"^[a-zA-Z0-9_\-\+\.]+$", token):
                names.append(token)

        # De-dup while preserving order
        out: List[str] = []
        seen = set()
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def available_ffmpeg_capabilities(self) -> dict:
        """
        Return a capability map of what the current ffmpeg binary supports.
        Used by Settings diagnostics and feature templates to expose 'magic' paths.
        """
        return {
            "encoders": self._scan_list_output(["-encoders"], "encoders"),
            "decoders": self._scan_list_output(["-decoders"], "decoders"),
            "filters": self._scan_list_output(["-filters"], "filters"),
            "formats": self._scan_list_output(["-formats"], "formats"),
            "protocols": self._scan_list_output(["-protocols"], "protocols"),
            "pix_fmts": self._scan_list_output(["-pix_fmts"], "pix_fmts"),
            "bsfs": self._scan_list_output(["-bsfs"], "bsfs"),
            "hwaccels": self._scan_list_output(["-hwaccels"], "hwaccels"),
        }

    def capabilities_summary_text(self) -> str:
        caps = self.available_ffmpeg_capabilities()
        lines = ["FFmpeg Capability Scan", ""]
        for key in ("encoders", "decoders", "filters", "formats", "protocols", "pix_fmts", "bsfs", "hwaccels"):
            items = caps.get(key, [])
            preview = ", ".join(items[:20])
            if len(items) > 20:
                preview += ", ..."
            lines.append(f"{key}: {len(items)}")
            if preview:
                lines.append(f"  {preview}")
        return "\n".join(lines)

    def is_available(self) -> bool:
        ok, _, _ = self.run([self.ffmpeg, "-version"], timeout=10)
        return ok

    def hardware_decode_args(self) -> List[str]:
        """Generic hwaccel for analysis/stream-copy operations (no encode)."""
        return ["-hwaccel", "auto"]

    def _gpu_full_pipeline_decode_args(self, codec: str) -> List[str]:
        """
        GPU-assisted decode args.  Frames are output to CPU memory so CPU
        filters (scale, eq, etc.) work reliably.  The GPU encoder (nvenc /
        qsv / amf) then accepts NV12/yuv420p frames directly.
        This gives GPU decode speed + GPU encode speed without the
        compatibility issues of keeping frames in GPU VRAM through filters.
        """
        if codec == "h264_nvenc":
            return ["-hwaccel", "cuda"]
        if codec == "h264_qsv":
            return ["-hwaccel", "qsv"]
        if codec == "h264_amf":
            return ["-hwaccel", "d3d11va"]
        return []

    def _gpu_scale_filter(self, codec: str, w: int, h: int) -> Optional[str]:
        """We use software scale for all codecs (reliable, fast enough for 1080p→480p)."""
        return None  # always use CPU scale + format conversion

    def _cpu_format_for_encoder(self, codec: str) -> Optional[str]:
        """Pixel format needed when feeding CPU-decoded frames to a GPU encoder."""
        if codec in ("h264_nvenc", "h264_qsv"):
            return "nv12"
        if codec in ("h264_amf", "h264_mf"):
            return "yuv420p"
        return None  # libx264 accepts whatever

    def hardware_encode_quality_args(self,
                                     codec: str,
                                     crf: int = 18,
                                     preset: str = "p4") -> List[str]:
        if codec == "h264_nvenc":
            cq = max(16, min(35, crf))
            return ["-preset", preset if preset.startswith("p") else "p4", "-cq", str(cq), "-b:v", "0"]
        if codec == "h264_qsv":
            qp = max(16, min(35, crf))
            return ["-preset", "medium", "-global_quality", str(qp)]
        if codec == "h264_amf":
            qp = max(16, min(35, crf))
            return ["-quality", "balanced", "-qp_i", str(qp), "-qp_p", str(qp)]
        if codec == "h264_mf":
            # Windows MediaFoundation H.264 encoder — uses GPU hardware on any Windows box.
            # rate_control 2 = unconstrained VBR; quality 0-100 (higher = better).
            quality = max(30, min(95, 100 - crf))  # invert crf scale
            return ["-rate_control", "2", "-quality", str(quality)]
        return ["-preset", preset if not preset.startswith("p") else "veryfast", "-crf", str(crf)]

    def _log_encoder_unavailable(self, codec: str, err: str) -> None:
        """Log a human-readable reason why a probe failed, with actionable advice."""
        if codec == "h264_nvenc":
            if "nvEncodeAPI64.dll" in err or "minimum required Nvidia driver" in err:
                import re
                m = re.search(r"minimum required Nvidia driver[^\d]*(\d+[\.\d]*)", err)
                required = m.group(1) if m else "570.0"
                log.warning(
                    f"Encoder probe SKIP: h264_nvenc — NVIDIA driver too old. "
                    f"Requires {required}+. Update at: https://www.nvidia.com/drivers  "
                    f"If GPU is too old for that driver, h264_mf (Windows MediaFoundation) "
                    f"will be used instead — it also uses hardware acceleration."
                )
            elif "no capable devices found" in err.lower() or "no nvidia" in err.lower():
                log.info("Encoder probe SKIP: h264_nvenc — no NVIDIA GPU detected")
            else:
                log.info(f"Encoder probe SKIP: h264_nvenc — {err.strip()[-200:]}")
        elif codec == "h264_qsv":
            if "device type qsv" in err or "No device available" in err:
                log.info("Encoder probe SKIP: h264_qsv — no Intel GPU/iGPU detected")
            else:
                log.info(f"Encoder probe SKIP: h264_qsv — {err.strip()[-200:]}")
        elif codec == "h264_amf":
            log.info("Encoder probe SKIP: h264_amf — no AMD GPU detected")
        else:
            log.info(f"Encoder probe SKIP: {codec} — not available on this system")

    def probe_working_encoders(self) -> List[str]:
        """
        Live-test each candidate encoder using a tiny lavfi testsrc.
        Results cached for the lifetime of this wrapper instance.
        Called once on first encode attempt; subsequent calls return cached results.
        """
        if self._working_h264_encoders is not None:
            return list(self._working_h264_encoders)

        # First filter by what's listed in -encoders output
        ok, stdout, _ = self.run([self.ffmpeg, "-hide_banner", "-encoders"], timeout=20)
        listed = set()
        if ok:
            listed = {c for c in self._ENCODER_CANDIDATES if c in stdout}
        listed.add("libx264")  # always available

        working = []
        for codec in self._ENCODER_CANDIDATES:
            if codec not in listed:
                continue
            fmt = self._cpu_format_for_encoder(codec) or "yuv420p"
            args = [
                self.ffmpeg, "-y",
                "-f", "lavfi", "-i", f"color=black:s=64x64:r=1:d=0.1",
                "-vf", f"format={fmt}",
                "-c:v", codec,
                "-frames:v", "3",
            ]
            args += self.hardware_encode_quality_args(codec, crf=28, preset="p1")
            args += ["-f", "null", "-"]
            probe_ok, _, err = self.run(args, timeout=15)
            if probe_ok:
                working.append(codec)
                log.info(f"Encoder probe OK: {codec}")
            else:
                # Check if it produced frames but exited non-zero (h264_mf quirk)
                if "frame=" in err and "Conversion failed" not in err:
                    working.append(codec)
                    log.info(f"Encoder probe OK (warned): {codec}")
                else:
                    self._log_encoder_unavailable(codec, err)

        if "libx264" not in working:
            working.append("libx264")
        self._working_h264_encoders = working
        log.info(f"Working H.264 encoders: {working}")
        return list(working)

    def preferred_h264_encoder(self) -> str:
        if self._preferred_h264_encoder is None:
            working = self.probe_working_encoders()
            # Pick best GPU encoder available; fall back to h264_mf then libx264
            for candidate in ["h264_nvenc", "h264_qsv", "h264_amf", "h264_mf", "libx264"]:
                if candidate in working:
                    self._preferred_h264_encoder = candidate
                    break
            else:
                self._preferred_h264_encoder = "libx264"
            log.info(f"Preferred H.264 encoder: {self._preferred_h264_encoder}")
        return self._preferred_h264_encoder

    def available_h264_encoders(self) -> List[str]:
        return self.probe_working_encoders()

    def _encoder_fallback_order(self) -> List[str]:
        preferred = self.preferred_h264_encoder()
        working = self.probe_working_encoders()
        ordered = [preferred] + [c for c in working if c != preferred]
        # De-dup while preserving order
        out: List[str] = []
        seen: set = set()
        for c in ordered:
            if c not in seen:
                out.append(c)
                seen.add(c)
        if "libx264" not in seen:
            out.append("libx264")
        return out

    def _run_h264_with_fallback(self,
                                build_args,
                                timeout: int,
                                context: str) -> bool:
        """
        Try encoders in priority order (best GPU first, libx264 last).
        Only encoders that passed the startup probe are attempted.
        For GPU encoders: try with GPU-assisted decode first, then CPU-only decode.
        For h264_mf / libx264: only CPU decode (no GPU decode overhead).
        build_args(codec: str, use_hwdecode: bool) -> List[str]
        """
        preferred = self.preferred_h264_encoder()
        last_err = ""
        GPU_DECODABLE = {"h264_nvenc", "h264_qsv", "h264_amf"}

        for codec in self._encoder_fallback_order():
            decode_modes = (True, False) if codec in GPU_DECODABLE else (False,)
            for use_hwdecode in decode_modes:
                args = build_args(codec, use_hwdecode)
                ok, _, err = self.run(args, timeout=timeout)
                if ok:
                    if codec != preferred or use_hwdecode is False:
                        mode = "gpu-decode" if use_hwdecode else "cpu-decode"
                        log.info(f"{context}: using {codec} ({mode}).")
                    return True
                last_err = err
                mode = "gpu-decode" if use_hwdecode else "cpu-decode"
                log.warning(f"{context}: {codec} ({mode}) failed. Trying next…")

        if last_err:
            log.warning(f"{context}: all encoder fallbacks exhausted. Last error: {last_err[-350:]}")
        return False


    def clear_cache(self):
        with _CACHE_LOCK:
            _INFO_CACHE.clear()
        self._available_h264_encoders = None
        self._working_h264_encoders = None
        self._preferred_h264_encoder = None


# ── Helpers ────────────────────────────────────────────────────────────────────
def _build_atempo_chain(speed: float) -> List[str]:
    """
    atempo only accepts 0.5–2.0.  Chain multiple atempo for extreme speeds.
    E.g. 8x → atempo=2.0,atempo=2.0,atempo=2.0
         0.25x → atempo=0.5,atempo=0.5
    """
    parts: List[str] = []
    remaining = speed
    if remaining > 1.0:
        while remaining > 2.0:
            parts.append("atempo=2.0")
            remaining /= 2.0
        parts.append(f"atempo={remaining:.4f}")
    elif remaining < 1.0:
        while remaining < 0.5:
            parts.append("atempo=0.5")
            remaining *= 2.0
        parts.append(f"atempo={remaining:.4f}")
    return parts


# Module-level singleton
ffmpeg = FFmpegWrapper()
