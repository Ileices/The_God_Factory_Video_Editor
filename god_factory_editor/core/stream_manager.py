"""
StreamManager — loads a video file and extracts its metadata via ffprobe.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from god_factory_editor.models.video_file import VideoMetadata
from god_factory_editor.utils.ffmpeg_wrapper import FFmpegWrapper, ffmpeg as _default_ffmpeg
from god_factory_editor.utils.file_utils import is_video_file
from god_factory_editor.utils.logger import log


class StreamManager:
    """
    Responsible for:
    - Validating and loading a video file
    - Extracting duration, resolution, fps, codec via ffprobe
    - Providing the current VideoMetadata to the rest of the app
    """

    def __init__(self, ff: Optional[FFmpegWrapper] = None):
        self._ff = ff or _default_ffmpeg
        self.metadata: Optional[VideoMetadata] = None

    # ── Load ──────────────────────────────────────────────────────────────────
    def load(self, path: Path) -> VideoMetadata:
        """
        Load a video file.  Raises ValueError with a user-friendly message on error.
        """
        path = Path(path)

        if not path.exists():
            raise ValueError(f"File not found:\n{path}")

        if not is_video_file(path):
            raise ValueError(
                f"'{path.suffix}' is not a supported video format.\n"
                "Supported: MP4, MKV, MOV, AVI, TS, M4V, WebM"
            )

        info = self._ff.get_video_info(path)
        if info is None:
            raise ValueError(
                "Could not read video information.\n"
                "The file may be corrupted or an unsupported codec is used."
            )

        meta = self._parse_probe(path, info)
        log.info(
            f"Loaded: {path.name} | "
            f"{meta.resolution_str} | {meta.duration_str} | "
            f"{meta.fps:.2f} fps | {meta.codec}"
        )

        # Warn for very large files
        if meta.file_size > 50 * 1024 ** 3:
            log.warning("Very large file (>50 GB). Proxy mode is recommended.")

        self.metadata = meta
        return meta

    # ── Parse ffprobe JSON ────────────────────────────────────────────────────
    @staticmethod
    def _parse_probe(path: Path, info: dict) -> VideoMetadata:
        meta = VideoMetadata(path=path)
        meta.file_size = path.stat().st_size

        # Duration from format
        fmt = info.get("format", {})
        try:
            meta.duration = float(fmt.get("duration", 0))
        except (TypeError, ValueError):
            pass

        try:
            meta.bitrate = int(fmt.get("bit_rate", 0))
        except (TypeError, ValueError):
            pass

        # Streams
        for stream in info.get("streams", []):
            codec_type = stream.get("codec_type", "")
            if codec_type == "video" and not meta.codec:
                meta.codec = stream.get("codec_name", "")
                try:
                    meta.width = int(stream.get("width", 0))
                    meta.height = int(stream.get("height", 0))
                except (TypeError, ValueError):
                    pass

                # fps — try r_frame_rate first, then avg_frame_rate
                for fps_key in ("r_frame_rate", "avg_frame_rate"):
                    fps_str = stream.get(fps_key, "")
                    if fps_str and fps_str != "0/0":
                        try:
                            num, den = fps_str.split("/")
                            if int(den):
                                meta.fps = round(int(num) / int(den), 3)
                                break
                        except Exception:
                            pass

                # Duration override from stream if format had none
                if not meta.duration:
                    try:
                        meta.duration = float(stream.get("duration", 0))
                    except (TypeError, ValueError):
                        pass

            elif codec_type == "audio" and not meta.audio_codec:
                meta.audio_codec = stream.get("codec_name", "")
                meta.has_audio = True

        return meta

    def unload(self):
        self.metadata = None
        self._ff.clear_cache()
