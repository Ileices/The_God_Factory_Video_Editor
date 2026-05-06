# The God Factory Video Editor

Turn long gaming streams into clean, publish-ready clip batches fast.

You can load 8-16 hour recordings, mark moments with I/O keys, auto-detect scenes,
auto-cut boring parts, then export selected clips in fast copy mode or frame-accurate
re-encode mode.

## Highlights

- Fast clip workflow: I/O marking, split, merge, rename, tags, difficulty, undo/redo.
- Smart timeline: draggable clips, playhead seek, zoom, fit-to-window, source previews.
- Subtitle support: imports `.vtt`, `.srt`, `.sbv` and aligns captions to clips.
- GPU-aware pipeline: proxy generation and encode/decode fallback chain.
- Auto tools: scene detection, transition suggestions, SFX suggestions, auto-captions.
- Rich progress UX: animated progress bars, ETA, and rotating help tips.
- Project persistence: save/load `.gfve`, auto-save recovery.

## Source Update Features

Settings -> Tools & FFmpeg now includes:

- Check Update Status (remote vs local branch)
- Pull Latest Updates Now (safe fast-forward only)
- Clone Latest Source (fresh checkout to selected folder)
- Optional pull-on-launch behavior

The updater refuses to pull over uncommitted local changes.

## FFmpeg Bootstrap Features

When bundled FFmpeg binaries are missing, the app can:

- Auto-bootstrap FFmpeg on launch from a configured zip URL
- Manually install/update FFmpeg from Settings
- Validate FFmpeg availability/version from the same panel

## Safety Notes

- Runtime/user data should not be committed (imports, exports, saves, local envs).
- Large FFmpeg executables are intentionally ignored by GitHub pushes.

## Project Spec

See `SPEC.md` for complete architecture, feature matrix, workflows, and performance targets.
