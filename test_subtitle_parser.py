#!/usr/bin/env python3
"""
Quick test of subtitle parser functionality
"""

import sys
from pathlib import Path

# Add god_factory_editor to path
sys.path.insert(0, str(Path(__file__).parent))

from god_factory_editor.utils.subtitle_parser import parse_subtitle_file, merge_captions

def test_parsers():
    """Test parsing of all subtitle formats."""
    test_dir = Path(__file__).parent
    
    print("Testing subtitle parser...\n")
    
    # Test VTT
    print("=" * 60)
    print("Testing .vtt (WebVTT)")
    print("=" * 60)
    try:
        vtt_path = test_dir / "test_captions.vtt"
        captions = parse_subtitle_file(vtt_path)
        print(f"Loaded {len(captions)} captions from {vtt_path.name}")
        for i, cap in enumerate(captions, 1):
            print(f"\n  Caption {i}:")
            print(f"    Start: {cap['start']:.3f}s")
            print(f"    End: {cap['end']:.3f}s")
            print(f"    Text: {cap['text'][:50]}...")
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test SRT
    print("\n" + "=" * 60)
    print("Testing .srt (SubRip)")
    print("=" * 60)
    try:
        srt_path = test_dir / "test_captions.srt"
        captions = parse_subtitle_file(srt_path)
        print(f"Loaded {len(captions)} captions from {srt_path.name}")
        for i, cap in enumerate(captions, 1):
            print(f"\n  Caption {i}:")
            print(f"    Start: {cap['start']:.3f}s")
            print(f"    End: {cap['end']:.3f}s")
            print(f"    Text: {cap['text'][:50]}...")
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test SBV
    print("\n" + "=" * 60)
    print("Testing .sbv (YouTube SBV)")
    print("=" * 60)
    try:
        sbv_path = test_dir / "test_captions.sbv"
        captions = parse_subtitle_file(sbv_path)
        print(f"Loaded {len(captions)} captions from {sbv_path.name}")
        for i, cap in enumerate(captions, 1):
            print(f"\n  Caption {i}:")
            print(f"    Start: {cap['start']:.3f}s")
            print(f"    End: {cap['end']:.3f}s")
            print(f"    Text: {cap['text'][:50]}...")
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test merge_captions
    print("\n" + "=" * 60)
    print("Testing caption merge/alignment")
    print("=" * 60)
    try:
        vtt_path = test_dir / "test_captions.vtt"
        captions = parse_subtitle_file(vtt_path)
        
        # Merge with a clip spanning 2-10 seconds
        merged = merge_captions(
            captions,
            start_offset=0.0,
            clip_start=2.0,
            clip_end=10.0,
        )
        print(f"Original: {len(captions)} captions")
        print(f"After merge to clip [2.0, 10.0]: {len(merged)} captions")
        for i, cap in enumerate(merged, 1):
            print(f"\n  Merged Caption {i}:")
            print(f"    Start: {cap['start']:.3f}s (relative to clip)")
            print(f"    End: {cap['end']:.3f}s")
            print(f"    Text: {cap['text']}")
    except Exception as e:
        print(f"ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_parsers()
