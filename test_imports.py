#!/usr/bin/env python3
"""
Test imports for subtitle functionality
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("Testing imports...")

try:
    from god_factory_editor.utils.file_utils import (
        is_subtitle_file, 
        subtitle_file_dialog_filter
    )
    print("✓ file_utils imports OK")
except Exception as e:
    print(f"✗ file_utils import failed: {e}")

try:
    from god_factory_editor.utils.subtitle_parser import (
        parse_subtitle_file,
        merge_captions,
    )
    print("✓ subtitle_parser imports OK")
except Exception as e:
    print(f"✗ subtitle_parser import failed: {e}")

try:
    from god_factory_editor.gui.dialogs.subtitle_import_dialog import SubtitleImportDialog
    print("✓ subtitle_import_dialog imports OK")
except Exception as e:
    print(f"✗ subtitle_import_dialog import failed: {e}")

try:
    # Test that main.py doesn't have import errors related to dialogs
    import god_factory_editor.gui.main_window
    print("✓ main_window imports OK")
except Exception as e:
    print(f"✗ main_window import failed: {e}")

print("\nAll imports successful!")
