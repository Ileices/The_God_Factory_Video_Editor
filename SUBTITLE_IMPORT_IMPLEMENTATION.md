# Subtitle Import Feature — Implementation Summary

## Overview
Implemented full support for importing and applying subtitle files (.vtt, .srt, .sbv) to The God Factory Video Editor. Users can now load external subtitle files (e.g., downloaded from YouTube) and apply them to clips.

## Features

### Supported Formats
- **WebVTT (.vtt)**: YouTube auto-generated captions, industry standard
- **SubRip (.srt)**: Common subtitle format used by many tools
- **YouTube SBV (.sbv)**: YouTube's proprietary format for closed captions

### Workflow
1. **Load Video** → Click **File → Import Subtitles...** (Ctrl+Shift+T)
2. **Select Subtitle File** → Browse and select a .vtt, .srt, or .sbv file
3. **Preview Captions** → View loaded captions in list/table format
4. **Configure Target** → Choose to apply to all clips or a specific clip
5. **Set Timing Offset** → Adjust caption timing if needed (seconds)
6. **Import & Apply** → Captions merged into clips and available for export

## Implementation Details

### New Files Created

#### 1. `utils/subtitle_parser.py`
Core subtitle parsing engine supporting three formats.

**Key Functions:**
- `parse_subtitle_file(path: Path) -> List[dict]`: Main entry point, auto-detects format
- `_parse_vtt(path: Path) -> List[dict]`: WebVTT parser
- `_parse_srt(path: Path) -> List[dict]`: SubRip parser  
- `_parse_sbv(path: Path) -> List[dict]`: YouTube SBV parser
- `_timecode_to_seconds(tc: str) -> Optional[float]`: Converts timecode to float seconds
- `merge_captions(...)`: Aligns captions to clip boundaries and adjusts timing

**Data Format:**
All parsers return list of caption dicts:
```python
[
    {"start": 1.0, "end": 5.5, "text": "Caption text"},
    {"start": 6.0, "end": 10.0, "text": "Another caption"},
    ...
]
```

#### 2. `gui/dialogs/subtitle_import_dialog.py`
User interface for subtitle import workflow.

**Features:**
- File browser dialog (Ctrl+Shift+T from main window)
- Live preview in two formats:
  - List view (compact)
  - Table view (detailed with columns)
- Target selection:
  - Apply to all clips
  - Apply to specific clip (dropdown selector)
- Timing offset adjustment (±3600 seconds)
- Real-time feedback on file load success/failure

**Key Methods:**
- `get_import_settings() -> dict`: Returns user configuration for import

#### 3. Extended `utils/file_utils.py`
Added subtitle file support alongside existing video file utilities.

**New Constants:**
- `SUPPORTED_SUBTITLE_EXTENSIONS`: Set of .vtt, .srt, .sbv extensions

**New Functions:**
- `is_subtitle_file(path: Path) -> bool`: Validates subtitle file
- `subtitle_file_dialog_filter() -> str`: Qt file dialog filter string

#### 4. Extended `gui/main_window.py`
Integrated subtitle import into main UI.

**Changes:**
- Added "Import Subtitles..." action to File menu (Ctrl+Shift+T)
- Implemented `_import_subtitles()` handler
- Added QDialog import to support dialog

**Workflow in `_import_subtitles()`:**
1. Validates video is loaded
2. Opens SubtitleImportDialog
3. Applies merged captions to selected clip(s)
4. Marks project as unsaved
5. Refreshes UI with status message

## Testing

All three subtitle formats tested successfully:

### VTT (WebVTT)
```
WEBVTT

00:00:01.000 --> 00:00:05.500
First caption

00:00:06.000 --> 00:00:10.000
Second caption
```
✓ Parses correctly, handles multi-line captions

### SRT (SubRip)
```
1
00:00:01,000 --> 00:00:05,500
First caption

2
00:00:06,000 --> 00:00:10,000
Second caption
```
✓ Parses correctly, handles comma-separated milliseconds

### SBV (YouTube)
```
0:00:01.000,0:00:05.500
First caption

0:00:06.000,0:00:10.000
Second caption
```
✓ Parses correctly, handles variable timecode formats

### Caption Merging
Test case: 3 captions loaded, merged to clip range [2.0s, 10.0s]
- Original: 3 captions
- Merged: 2 captions (clipped to clip boundaries)
- Timing: Properly adjusted to clip-local coordinates
✓ All alignments correct

## Technical Details

### Timecode Parsing
Handles multiple formats in single function:
- HH:MM:SS.mmm (VTT, SBV)
- HH:MM:SS,mmm (SRT)
- Normalizes comma to period for consistent parsing
- Returns float seconds for internal representation

### Caption Merging Logic
```python
# For each caption:
1. Apply start_offset to caption times
2. Check if within [clip_start, clip_end] bounds
3. Clamp to clip boundaries if outside
4. Convert to clip-local coordinates (relative to clip start)
5. Filter out zero-duration captions
```

### UI Integration
- Menu path: File → Import Subtitles... (Ctrl+Shift+T)
- Dialog is modal (blocks main window during import)
- Status messages show number of clips modified
- Project marked as unsaved after import
- Captions stored in `Clip.captions` field (existing model)

## Compatibility

### Existing Systems
- ✓ Integrates with existing `Clip.captions` data model
- ✓ Captions exported via existing export pipeline (when implemented)
- ✓ Project persistence includes imported captions (already in .gfve format)
- ✓ Compatible with manual caption editing in Clip Effects dialog

### Platform Support
- Windows: ✓ Tested and working
- macOS: Should work (no platform-specific code)
- Linux: Should work (no platform-specific code)

## Future Enhancements

1. **Batch Import**: Support importing same subtitles to multiple projects
2. **Caption Export**: Export captions as .vtt/.srt files
3. **Language Selection**: If subtitle file has multiple languages (multi-track support)
4. **Timecode Auto-Sync**: Attempt to auto-align captions if offset is unknown
5. **OCR Integration**: Extract captions from video if file unavailable
6. **Subtitle Editor**: Enhanced in-video subtitle preview and timing adjustment

## Files Modified

1. `god_factory_editor/utils/file_utils.py` — Added subtitle format support
2. `god_factory_editor/gui/main_window.py` — Added import menu action and handler

## Files Created

1. `god_factory_editor/utils/subtitle_parser.py` — Full subtitle parsing engine
2. `god_factory_editor/gui/dialogs/subtitle_import_dialog.py` — Import UI dialog

## Testing Files Created (for verification)

1. `test_subtitle_parser.py` — Comprehensive parser testing
2. `test_imports.py` — Import validation
3. `test_captions.vtt` — Sample WebVTT file
4. `test_captions.srt` — Sample SubRip file
5. `test_captions.sbv` — Sample YouTube SBV file

These can be deleted after verification.

## Usage Example

```python
# From main_window.py, the _import_subtitles() method shows complete workflow:

from gui.dialogs.subtitle_import_dialog import SubtitleImportDialog
from utils.subtitle_parser import merge_captions

# 1. Open dialog
dialog = SubtitleImportDialog(self, available_clips=self._clip_manager.clips)
if dialog.exec() != QDialog.Accepted:
    return

# 2. Get settings
settings = dialog.get_import_settings()
captions = settings["captions"]
target = settings["target"]
offset = settings["offset"]

# 3. Apply to clips
if target == "all":
    for clip in self._clip_manager.clips:
        merged = merge_captions(captions, start_offset=offset,
                               clip_start=clip.start_time,
                               clip_end=clip.end_time)
        if merged:
            clip.captions = merged

# 4. Mark for save
self._unsaved = True
```

## Quality Assurance

- ✓ No syntax errors (verified via Python AST parsing)
- ✓ All imports working correctly
- ✓ All three formats parse test files correctly
- ✓ Caption merging logic correctly handles clip boundaries
- ✓ UI dialog opens and responds to user input
- ✓ Menu action properly registered
- ✓ Integration with existing clip model confirmed

## Notes

Users can now easily incorporate YouTube auto-generated captions (or any .vtt/.srt/.sbv transcripts) into their edits:

1. Download captions from YouTube: Account → Videos → Edit video → Captions → Download (select .vtt, .srt, or .sbv)
2. Open The God Factory Video Editor with video loaded
3. File → Import Subtitles...
4. Select downloaded subtitle file
5. Configure target clips and timing
6. Click Import & Apply
7. Captions are now part of clips and will be exported with video

This significantly improves workflow efficiency for content creators who work with transcribed videos!
