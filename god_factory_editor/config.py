"""
Configuration constants and user settings for The God Factory Video Editor.
Settings are persisted to %APPDATA%/GodFactoryEditor/settings.json
"""

import json
import os
import sys
from pathlib import Path

# ─── App Identity ─────────────────────────────────────────────────────────────
APP_NAME = "The God Factory Video Editor"
APP_VERSION = "1.0.0"
PROJECT_EXTENSION = ".gfve"

# ─── Paths ────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent.parent

RESOURCES_DIR = APP_DIR / "resources"
STYLES_DIR = RESOURCES_DIR / "styles"
ICONS_DIR = RESOURCES_DIR / "icons"
FFMPEG_DIR = RESOURCES_DIR / "ffmpeg"

APPDATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "GodFactoryEditor"
TEMP_DIR = APPDATA_DIR / "temp"
PROXIES_DIR = TEMP_DIR / "proxies"
THUMBNAILS_DIR = TEMP_DIR / "thumbnails"
LOGS_DIR = APPDATA_DIR / "logs"
SETTINGS_FILE = APPDATA_DIR / "settings.json"

# Create runtime dirs
for _d in (APPDATA_DIR, TEMP_DIR, PROXIES_DIR, THUMBNAILS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ─── FFmpeg ───────────────────────────────────────────────────────────────────
FFMPEG_EXE = FFMPEG_DIR / "ffmpeg.exe"
FFPROBE_EXE = FFMPEG_DIR / "ffprobe.exe"

# Fall back to system PATH if bundled binary not present
if not FFMPEG_EXE.exists():
    FFMPEG_EXE = Path("ffmpeg")
if not FFPROBE_EXE.exists():
    FFPROBE_EXE = Path("ffprobe")

# ─── Defaults ─────────────────────────────────────────────────────────────────
DEFAULTS = {
    "theme": "dark",
    "proxy_enabled": True,
    "proxy_resolution": [854, 480],
    "auto_save_interval": 30,       # seconds
    "seek_step_small": 5.0,         # Left/Right arrow
    "seek_step_large": 30.0,        # Shift+Left/Right
    "max_undo_steps": 50,
    "recent_files": [],
    "export_output_dir": str(Path.home() / "Videos" / "GodFactoryExports"),
    "export_preset": "fast",        # fast | accurate | youtube | archive
    "scene_detect_threshold": 27.0,
    "scene_min_duration": 15.0,     # seconds — ignore scenes shorter than this
    "proxy_max_age_days": 7,
    "timeline_zoom": 10.0,          # pixels per second
    "volume": 0.80,
    "repo_url": "https://github.com/Ileices/The_God_Factory_Video_Editor.git",
    "repo_auto_update_on_launch": False,
    "repo_auto_check_on_launch": True,
    "repo_clone_target_dir": str(Path.home() / "Documents"),
    "ffmpeg_auto_bootstrap_on_launch": True,
    "ffmpeg_download_url": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "shortcuts": {
        "play_pause": "Space",
        "mark_in": "I",
        "mark_out": "O",
        "seek_back": "Left",
        "seek_forward": "Right",
        "seek_back_large": "Shift+Left",
        "seek_forward_large": "Shift+Right",
        "split": "S",
        "delete": "Delete",
        "undo": "Ctrl+Z",
        "redo": "Ctrl+Y",
        "save": "Ctrl+S",
        "open": "Ctrl+O",
        "import_external_project": "Ctrl+Alt+O",
        "export_selected": "Ctrl+E",
        "export_all": "Ctrl+Shift+E",
        "auto_detect": "Ctrl+D",
        "automation_wizard": "Ctrl+Alt+W",
        "decibel_scan": "Ctrl+Alt+L",
        "toggle_proxy": "Ctrl+P",
        "loop_clip": "L",
        "rename": "F2",
        "zoom_in": "Ctrl+=",
        "zoom_out": "Ctrl+-",
        "fit_timeline": "F",
        "help": "F1",
    },
}

# ─── Export Presets ───────────────────────────────────────────────────────────
EXPORT_PRESETS = {
    "fast": {
        "label": "Fast (Stream Copy)",
        "description": "Near-instant export. No quality loss. Cuts may be ±1 frame.",
        "video_codec": "copy",
        "audio_codec": "copy",
        "resolution": None,   # keep original
        "accurate_seek": False,
    },
    "accurate": {
        "label": "Accurate (Re-encode)",
        "description": "Frame-perfect cuts. Slower. Uses H.264.",
        "video_codec": "libx264",
        "audio_codec": "aac",
        "crf": 18,
        "preset_speed": "veryfast",
        "resolution": None,
        "accurate_seek": True,
    },
    "youtube": {
        "label": "YouTube 1080p",
        "description": "Optimised for YouTube upload. H.264, 1080p max.",
        "video_codec": "libx264",
        "audio_codec": "aac",
        "crf": 20,
        "preset_speed": "fast",
        "resolution": [1920, 1080],
        "accurate_seek": True,
    },
    "archive": {
        "label": "Archive 4K (Lossless)",
        "description": "Full quality 4K copy. Large file sizes.",
        "video_codec": "copy",
        "audio_codec": "copy",
        "resolution": None,
        "accurate_seek": False,
    },
}

# ─── UI Colours (also in dark.qss; kept here for programmatic use) ────────────
COLOURS = {
    "bg_deep":       "#0b0f0a",
    "bg_surface":    "#131914",
    "bg_elevated":   "#1d2620",
    "accent_gold":   "#8fae3b",
    "accent_amber":  "#6f8d2a",
    "text_primary":  "#d7e0cf",
    "text_secondary":"#87937e",
    "border":        "#31402f",
    "clip_normal":   "#4b6b35",
    "clip_selected": "#8fae3b",
    "clip_exported": "#5d8a42",
    "clip_failed":   "#8a3f3f",
    "playhead":      "#c96d3a",
    "success":       "#5d8a42",
    "warning":       "#8c7a2d",
    "error":         "#8a3f3f",
}

# ─── Settings manager ─────────────────────────────────────────────────────────
class Settings:
    """Simple flat JSON settings store."""

    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        self._data = dict(DEFAULTS)
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._deep_update(self._data, saved)
            except Exception:
                pass  # silently use defaults

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    def get_shortcut(self, action: str) -> str:
        return self._data.get("shortcuts", {}).get(action, "")

    def _deep_update(self, base: dict, override: dict):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._deep_update(base[k], v)
            else:
                base[k] = v


# Singleton instance
settings = Settings()
