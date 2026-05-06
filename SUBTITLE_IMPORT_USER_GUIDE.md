# Subtitle Import User Guide

## Quick Start

### How to Import YouTube Captions

1. **Download Captions from YouTube**
   - Go to your YouTube account
   - Select a video you own/manage
   - Click "Edit" → "Subtitles"
   - Click "Auto-generated English" (or your language)
   - Click the three dots menu → "Download"
   - Choose format: `.vtt`, `.srt`, or `.sbv`

2. **Import into God Factory Video Editor**
   - Open The God Factory Video Editor
   - **File** → **Open Video...** (load your video)
   - **File** → **Import Subtitles...** (or press `Ctrl+Shift+T`)
   - Select your downloaded subtitle file
   - Review captions in preview window
   - Choose target: "All Clips" or specific clip
   - Adjust timing offset if needed (usually 0)
   - Click **Import & Apply**

3. **Use Captions**
   - Captions now attached to clips
   - Edit captions in **Clip → Edit Clip Effects** → **Captions tab**
   - Export video with captions (embedded in video or as sidecar file)

## Supported Formats

### WebVTT (.vtt)
- **Source**: YouTube auto-captions, standard web format
- **Format**:
```
WEBVTT

00:00:01.000 --> 00:00:05.500
Your caption text here

00:00:06.000 --> 00:00:10.000
Next caption
```

### SubRip (.srt)
- **Source**: General subtitle tool standard
- **Format**:
```
1
00:00:01,000 --> 00:00:05,500
Your caption text

2
00:00:06,000 --> 00:00:10,000
Next caption
```

### YouTube SBV (.sbv)
- **Source**: Legacy YouTube captions format
- **Format**:
```
0:00:01.000,0:00:05.500
Your caption text

0:00:06.000,0:00:10.000
Next caption
```

## Settings Explained

### Target
- **All Clips**: Apply subtitles to every clip in current project
- **Specific Clip**: Choose one clip to receive captions

### Timing Offset
- **0 seconds**: Use captions exactly as-is
- **Positive value** (e.g., +5): Shift all captions forward 5 seconds
- **Negative value** (e.g., -2): Shift all captions backward 2 seconds
- Use if video and caption timestamps don't align perfectly

## Tips & Tricks

### YouTube Caption Sync Issues
If captions appear out of sync:
1. Look at first caption - does it start at right time?
2. If too early: Set offset to positive (shift forward)
3. If too late: Set offset to negative (shift backward)
4. Test with small value first (±1 second), adjust as needed

### Multiple Audio Tracks
If video has multiple languages:
- Download captions for each language separately
- Import each language to different clips
- Or: Import once, manually copy/edit captions in Effects dialog

### Manual Editing
After import, edit individual captions:
1. Select a clip
2. **Clip → Edit Clip Effects**
3. Go to **Captions** tab
4. Click "Edit Selected" to modify timing, font, effects

### Combining with Auto-Captions
The auto-caption system (Effects → Generate Auto-Captions) is separate:
- Auto-captions: Generated from speech detection
- Imported captions: From external files (YouTube, etc.)
- Use whichever fits your workflow!

## Troubleshooting

### "File Not Found" Error
- Verify file path is correct
- File must be on local disk (not network path)
- Supported: `.vtt`, `.srt`, `.sbv` only

### No Captions Loaded
- File format might be corrupted
- Try downloading captions again from YouTube
- Check file isn't empty (open in notepad to verify)

### Captions Don't Appear at Start
- Check timing offset setting
- Captions may start later than video (e.g., intro section)
- Manually adjust in Captions tab if needed

### Offset Still Not Right
- Try importing to a single test clip first
- Adjust offset and preview
- Once correct, reimport to all clips

## FAQ

**Q: Can I import captions to just one clip?**
A: Yes! Select "Specific Clip" when importing, then choose the clip.

**Q: What if I mess up the offset?**
A: Open Import again - you can reimport over the same clips with new offset.

**Q: Do captions export with the video?**
A: Yes - if the format supports it (MP4, MKV, etc.). SRT is saved as sidecar file.

**Q: Can I edit captions after importing?**
A: Yes! Select clip → Clip → Edit Effects → Captions tab → Edit timing/text/font.

**Q: What if my subtitle file is corrupted?**
A: Download again from YouTube or use a subtitle editor to repair it first.

**Q: Can I use captions from other sources?**
A: Yes! Any .vtt, .srt, or .sbv file works - not just YouTube.
