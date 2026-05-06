# The God Factory Video Editor — Project Specification
### Version 1.0 | May 2026 | Built for: Windows 10 / 11

---

## 1. WHAT THIS APP DOES

You have 8–16 hour gaming live streams (4K/1080p). You need to cut out specific challenge segments and export them as separate videos to post on YouTube. This app makes that process fast, easy, and beautiful.

**Core promise:** Load a 16-hour stream → mark your clips → export them all in under a minute (fast mode, no re-encoding).

---

## 2. HOW TO RUN ON ANY COMPUTER (SETUP STEPS)

### One-Time Setup
1. Double-click **`setup.bat`**
2. Wait for it to finish (installs Python, downloads FFmpeg, installs all libraries)
3. Done — it creates a desktop shortcut for you

### Every Time You Want To Edit
- Double-click **`The God Factory Video Editor.bat`** (or use the desktop shortcut)

### Build a Standalone .EXE (Optional)
- Double-click **`build_exe.bat`**
- Creates `dist\The God Factory Video Editor.exe` — copy this to any PC and run it directly

---

## 3. PROJECT DIRECTORY STRUCTURE

```
the_god_factory_video/
├── SPEC.md                              ← You are here
├── setup.bat                            ← ONE-CLICK SETUP
├── The God Factory Video Editor.bat     ← ONE-CLICK LAUNCHER
├── build_exe.bat                        ← BUILDS STANDALONE .EXE
├── make_shortcut.vbs                    ← Creates desktop shortcut
├── requirements.txt                     ← Python packages
│
├── god_factory_editor/                  ← MAIN APP PACKAGE
│   ├── main.py                          ← Entry point
│   ├── config.py                        ← Settings, constants, presets
│   │
│   ├── models/                          ← DATA STRUCTURES
│   │   ├── clip.py                      ← Clip dataclass (start, end, name, tags...)
│   │   ├── video_file.py                ← VideoMetadata dataclass
│   │   └── project_data.py             ← Project save/load (JSON .gfve format)
│   │
│   ├── utils/                           ← LOW-LEVEL TOOLS
│   │   ├── logger.py                    ← Debug logging, crash reports
│   │   ├── time_utils.py               ← Timecode parsing / formatting
│   │   ├── file_utils.py               ← File validation, sanitization
│   │   ├── ffmpeg_wrapper.py           ← Direct FFmpeg subprocess calls
│   │   └── thumbnail_gen.py            ← Frame extraction to QImage
│   │
│   ├── core/                            ← BUSINESS LOGIC
│   │   ├── stream_manager.py           ← Load video, extract metadata
│   │   ├── clip_manager.py             ← CRUD on clips, undo/redo, signals
│   │   ├── proxy_manager.py            ← 480p proxy generation & caching
│   │   ├── export_engine.py            ← FFmpeg batch export (fast/accurate)
│   │   └── scene_detector.py           ← PySceneDetect auto-detection
│   │
│   └── gui/                             ← USER INTERFACE
│       ├── main_window.py              ← Main QMainWindow, layout, menus
│       ├── video_player.py             ← QMediaPlayer wrapper + controls
│       ├── timeline_widget.py          ← Custom painted timeline + clips
│       ├── clip_list_widget.py         ← Clip table with checkboxes
│       ├── export_dialog.py            ← Batch export UI + queue
│       ├── settings_dialog.py          ← App preferences
│       ├── help_window.py              ← Full interactive help system
│       └── dialogs/
│           ├── error_handler.py        ← User-friendly error dialogs
│           └── progress_dialog.py      ← Progress bar dialogs
│
├── resources/
│   ├── styles/
│   │   └── dark.qss                    ← Dark gold theme stylesheet
│   └── icons/                          ← App icons (generated at setup)
│
└── temp/                               ← Created at runtime
    ├── proxies/                        ← 480p preview copies
    └── thumbnails/                     ← Clip thumbnail frames
```

---

## 4. TECHNOLOGY STACK (May 2026)

| Component | Library | Version | Why |
|---|---|---|---|
| GUI Framework | PySide6 | 6.11+ | Official Qt Python binding, memory-leak-fixed, beautiful |
| Video Playback | PySide6 QMediaPlayer | Built-in | No extra install needed, handles 4K/1080p |
| Video Processing | FFmpeg 7.0 | Bundled | Industry standard, -c copy for fast export |
| Scene Detection | PySceneDetect | 0.6.7 | Auto-detects challenge cuts |
| Frame Extraction | OpenCV | 4.9+ | Fast thumbnail generation |
| Image Handling | Pillow | 10.1+ | Thumbnail resize / format conversion |
| System Monitoring | psutil | 5.9+ | Memory/disk usage warnings |
| Packaging | PyInstaller | 6.5+ | Single .exe, Python 3.14 + ARM64 support |

---

## 5. FEATURE LIST

### Must-Have (Core)
- [x] Load video files: MP4, MKV, MOV, AVI, TS
- [x] Play/pause/seek with keyboard shortcuts
- [x] Set in-point (I) and out-point (O) to mark clip start/end
- [x] Clip list with names, durations, checkboxes, export status
- [x] Custom visual timeline with draggable clips and playhead
- [x] Rename, delete, split, merge clips
- [x] Fast batch export (stream copy, near-instant)
- [x] Accurate export (re-encode for frame-perfect cuts)
- [x] Save / Load project files (.gfve format)
- [x] Auto-save every 30 seconds

### Advanced Features
- [x] Auto scene detection (finds challenge boundaries automatically)
- [x] 480p proxy generation for smooth 4K scrubbing
- [x] Loop region (A-B repeat for fine-tuning)
- [x] Undo/redo (50 steps)
- [x] Tagging system (win/loss/challenge type)
- [x] Clip difficulty rating (1–5 stars)
- [x] Export presets (Fast / Accurate / YouTube 1080p / Archive 4K)
- [x] Clip notes (per-clip text notes)
- [x] Hardware acceleration toggle
- [x] Export to multiple resolutions

### Ease of Use
- [x] **Full help system** — searchable, with clickable feature links
- [x] **In-app hints** — status bar tips + tooltips on every button
- [x] **Help bubbles** — "?" buttons on complex features open relevant help
- [x] **First-run wizard** — guides new users through their first clip
- [x] Drag-and-drop file loading
- [x] Recent files menu
- [x] Keyboard shortcuts reference (built into help)
- [x] Configurable shortcuts
- [x] Progress dialogs with ETA for all long operations
- [x] Error dialogs with plain-English messages and fix suggestions

### Visual Design
- [x] Dark theme (dark navy + gold accents)
- [x] Light theme toggle
- [x] Smooth timeline with gradient clip blocks
- [x] Thumbnail strip on timeline clips (optional)
- [x] Animated progress indicators
- [x] Status bar with live stats (time, memory, clip count)

---

## 6. KEYBOARD SHORTCUTS

| Key | Action |
|---|---|
| Space | Play / Pause |
| I | Mark In (set clip start) |
| O | Mark Out (set clip end) |
| Left Arrow | Jump back 5 seconds |
| Right Arrow | Jump forward 5 seconds |
| Shift+Left | Jump back 30 seconds |
| Shift+Right | Jump forward 30 seconds |
| S | Split clip at playhead |
| Delete | Delete selected clip |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+S | Save project |
| Ctrl+O | Open video file |
| Ctrl+E | Export selected clips |
| Ctrl+Shift+E | Export all clips |
| Ctrl+D | Auto-detect scenes |
| Ctrl+P | Toggle proxy mode |
| L | Loop current clip |
| F2 | Rename selected clip |
| Ctrl++ | Zoom timeline in |
| Ctrl+- | Zoom timeline out |
| F | Fit timeline to window |
| F1 | Open Help |

---

## 7. USER FLOWS

### Flow 1: First-Time User
1. Double-click setup.bat → wait for setup
2. Launch app → first-run wizard appears
3. Wizard: drag your video onto the window
4. Video loads, timeline appears
5. Press PLAY, find your challenge start
6. Press **I** to mark start → gold bar appears on timeline
7. Continue to challenge end → press **O**
8. Clip appears in list on the right
9. Click "Export Selected" → done in seconds

### Flow 2: Power User Workflow
1. Load 16-hour 4K stream → proxy auto-generates in background
2. Click "Auto-Detect" → 40+ scene cuts detected, offered as clip suggestions
3. Review suggestions, accept/reject each
4. Fine-tune boundaries by dragging clip edges on timeline
5. Tag clips (win/loss, challenge type)
6. Select all → Batch Export (fast mode) → all done in under 2 minutes

---

## 8. PROJECT FILE FORMAT (.gfve)

```json
{
  "version": "1.0",
  "app": "The God Factory Video Editor",
  "created": "2026-05-05T14:32:11Z",
  "modified": "2026-05-05T15:45:22Z",
  "video": {
    "path": "D:/Streams/2026-05-01_SoD2_4K.mp4",
    "duration": 43200.5,
    "resolution": [3840, 2160],
    "fps": 60.0,
    "codec": "h264",
    "proxy_path": "temp/proxies/abc123_480p.mp4"
  },
  "clips": [
    {
      "id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
      "start": 125.3,
      "end": 378.9,
      "name": "Challenge 1 - No Guns Run",
      "notes": "Died at 5:42, retry at 6:20",
      "tags": ["no_guns", "win"],
      "difficulty": 4,
      "export_status": "exported",
      "export_path": "D:/Exports/Challenge_1_No_Guns_Run.mp4"
    }
  ],
  "ui_state": {
    "timeline_zoom": 250.0,
    "playhead_position": 125.3,
    "volume": 0.75,
    "proxy_enabled": true
  }
}
```

---

## 9. PERFORMANCE TARGETS

| Operation | Target | Maximum |
|---|---|---|
| App startup | 2 seconds | 5 seconds |
| Load 4K video metadata | 0.5 seconds | 2 seconds |
| Seek in 16-hour 4K | 200ms | 800ms |
| Timeline render (100 clips) | 30ms | 100ms |
| Export 2-min clip (fast) | 2 seconds | 10 seconds |
| Scene detection (1 hour) | 3 minutes | 8 minutes |
| Memory usage (proxy on) | 1.5 GB | 2.5 GB |

---

## 10. BUILD ORDER (IMPLEMENTATION LEVELS)

```
LEVEL 0 — Foundation (must exist first)
  requirements.txt, config.py, utils/logger.py, utils/time_utils.py,
  utils/file_utils.py, models/clip.py, models/video_file.py

LEVEL 1 — Processing Core
  utils/ffmpeg_wrapper.py, utils/thumbnail_gen.py,
  core/stream_manager.py, core/clip_manager.py, core/proxy_manager.py

LEVEL 2 — Export & Detection
  core/export_engine.py, core/scene_detector.py, models/project_data.py

LEVEL 3 — GUI Foundation
  resources/styles/dark.qss, gui/dialogs/, gui/video_player.py

LEVEL 4 — Visual Editing
  gui/timeline_widget.py, gui/clip_list_widget.py

LEVEL 5 — Dialogs & Help
  gui/export_dialog.py, gui/settings_dialog.py, gui/help_window.py

LEVEL 6 — Integration
  gui/main_window.py, main.py
```

---

## 11. ERROR RECOVERY MATRIX

| Error | What the user sees | What happens |
|---|---|---|
| Video file not found | "Can't find video. Has it been moved?" + Browse button | File picker opens |
| FFmpeg missing | "Video tools not found. Click here to re-run setup" | Opens setup instructions |
| Disk full during export | "Not enough space. Need X GB. Free some space and retry." | Export paused, retries possible |
| Corrupted video | "This video may have damaged frames. Continue anyway?" | Partial load, warning shown |
| VLC/codec missing | "Can't play this format. Try proxy mode." | Switches to proxy |
| Export fails | "Failed to export [clip name]. Reason: [details]" | Other clips continue |
| Scene detection slow | "This is taking longer than usual. Keep waiting or cancel?" | Cancel saves partial results |
| App crash | On restart: "Recover your last session?" | Auto-save .gfve restored |

---

*This spec is the living document used to build The God Factory Video Editor.*
*Every feature described here is implemented in the `god_factory_editor/` package.*
