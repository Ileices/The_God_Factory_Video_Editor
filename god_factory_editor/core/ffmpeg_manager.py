"""
FFmpeg bootstrap/update manager.

Provides:
- detection of bundled ffmpeg/ffprobe binaries
- optional auto-bootstrap on launch
- manual install/update from a configured zip URL
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Tuple

from god_factory_editor.config import FFMPEG_DIR, settings


class FFmpegManager:
    def __init__(self, ffmpeg_dir: Path | None = None):
        self.ffmpeg_dir = Path(ffmpeg_dir or FFMPEG_DIR)
        self.ffmpeg_exe = self.ffmpeg_dir / "ffmpeg.exe"
        self.ffprobe_exe = self.ffmpeg_dir / "ffprobe.exe"

    def installed(self) -> bool:
        return self.ffmpeg_exe.exists() and self.ffprobe_exe.exists()

    def version(self) -> str:
        if not self.installed():
            return "Not installed"
        try:
            proc = subprocess.run(
                [str(self.ffmpeg_exe), "-version"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if proc.returncode != 0:
                return "Installed (version unknown)"
            line = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
            return line.strip() or "Installed"
        except Exception:
            return "Installed (version unknown)"

    def ensure_on_launch(self) -> Tuple[bool, str]:
        if self.installed():
            return True, f"FFmpeg ready: {self.version()}"
        if not settings.get("ffmpeg_auto_bootstrap_on_launch", True):
            return False, "Bundled FFmpeg is missing. Enable auto-bootstrap in Settings or install manually."
        return self.install_or_update()

    def install_or_update(self) -> Tuple[bool, str]:
        url = settings.get("ffmpeg_download_url", "").strip()
        if not url:
            return False, "FFmpeg download URL is empty in Settings."

        self.ffmpeg_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="godfactory_ffmpeg_") as td:
            tmp_zip = Path(td) / "ffmpeg_bundle.zip"
            try:
                urllib.request.urlretrieve(url, tmp_zip)
            except Exception as exc:
                return False, f"FFmpeg download failed: {exc}"

            try:
                with zipfile.ZipFile(tmp_zip, "r") as zf:
                    members = zf.namelist()
                    ffmpeg_member = next((m for m in members if m.lower().endswith("/ffmpeg.exe")), None)
                    ffprobe_member = next((m for m in members if m.lower().endswith("/ffprobe.exe")), None)
                    if not ffmpeg_member or not ffprobe_member:
                        return False, "Downloaded archive did not contain ffmpeg.exe and ffprobe.exe"

                    ffmpeg_tmp = Path(td) / "ffmpeg.exe"
                    ffprobe_tmp = Path(td) / "ffprobe.exe"

                    with zf.open(ffmpeg_member) as src, open(ffmpeg_tmp, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    with zf.open(ffprobe_member) as src, open(ffprobe_tmp, "wb") as dst:
                        shutil.copyfileobj(src, dst)

                    shutil.copy2(ffmpeg_tmp, self.ffmpeg_exe)
                    shutil.copy2(ffprobe_tmp, self.ffprobe_exe)
            except Exception as exc:
                return False, f"FFmpeg extraction failed: {exc}"

        if self.installed():
            return True, f"FFmpeg installed/updated successfully. {self.version()}"
        return False, "FFmpeg install completed but binaries were not found in target directory."
