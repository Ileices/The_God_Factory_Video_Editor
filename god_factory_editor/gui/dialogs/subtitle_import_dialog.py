"""
Subtitle Import Dialog — allows user to load and apply subtitle files to clips.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QListWidget, QListWidgetItem, QGroupBox,
    QMessageBox, QFileDialog, QTabWidget, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from god_factory_editor.utils.subtitle_parser import parse_subtitle_file, merge_captions
from god_factory_editor.utils.file_utils import subtitle_file_dialog_filter


class SubtitleImportDialog(QDialog):
    """Dialog for importing subtitle files and applying captions to clips."""
    
    def __init__(self, parent=None, available_clips: Optional[List] = None):
        super().__init__(parent)
        self.setWindowTitle("Import Subtitles")
        self.setGeometry(100, 100, 700, 600)
        self.setModal(True)
        
        self.available_clips = available_clips or []
        self.loaded_captions: List[dict] = []
        self.subtitle_path: Optional[Path] = None
        
        self._init_ui()
    
    def _init_ui(self):
        """Build the UI layout."""
        layout = QVBoxLayout(self)
        
        # ── File Selection ──────────────────────────────────────────────────
        file_group = QGroupBox("Subtitle File")
        file_layout = QHBoxLayout()
        
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #888; font-style: italic;")
        file_layout.addWidget(self.file_label, 1)
        
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(self.browse_btn)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # ── Preview Tabs ────────────────────────────────────────────────────
        tabs = QTabWidget()
        
        # Captions preview
        self.captions_list = QListWidget()
        tabs.addTab(self.captions_list, "Captions Preview")
        
        # Detailed table view
        self.captions_table = QTableWidget()
        self.captions_table.setColumnCount(3)
        self.captions_table.setHorizontalHeaderLabels(["Start", "End", "Text"])
        self.captions_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        tabs.addTab(self.captions_table, "Detailed View")
        
        layout.addWidget(tabs, 1)
        
        # ── Application Settings ────────────────────────────────────────────
        settings_group = QGroupBox("Apply To Clips")
        settings_layout = QHBoxLayout()
        
        settings_layout.addWidget(QLabel("Target:"))
        
        self.target_combo = QComboBox()
        self.target_combo.addItem("All Clips", "all")
        self.target_combo.addItem("Specific Clip", "specific")
        self.target_combo.currentIndexChanged.connect(self._on_target_changed)
        settings_layout.addWidget(self.target_combo)
        
        settings_layout.addSpacing(20)
        settings_layout.addWidget(QLabel("Timing Offset (seconds):"))
        
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(-3600, 3600)
        self.offset_spin.setValue(0)
        self.offset_spin.setMinimumWidth(80)
        settings_layout.addWidget(self.offset_spin)
        
        settings_layout.addStretch()
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # ── Specific Clip Selector ──────────────────────────────────────────
        self.clip_selector_group = QGroupBox("Select Clip")
        clip_layout = QHBoxLayout()
        
        self.clip_combo = QComboBox()
        self._populate_clip_combo()
        clip_layout.addWidget(self.clip_combo, 1)
        
        self.clip_selector_group.setLayout(clip_layout)
        self.clip_selector_group.setVisible(False)
        layout.addWidget(self.clip_selector_group)
        
        # ── Buttons ─────────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        
        self.import_btn = QPushButton("Import & Apply")
        self.import_btn.clicked.connect(self.accept)
        self.import_btn.setEnabled(False)
        btn_layout.addStretch()
        btn_layout.addWidget(self.import_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def _populate_clip_combo(self):
        """Populate the clip selector with available clips."""
        self.clip_combo.clear()
        for i, clip in enumerate(self.available_clips):
            label = f"{clip.name or f'Clip {i+1}'} ({clip.start_str} – {clip.end_str})"
            self.clip_combo.addItem(label, clip.id)
    
    def _on_target_changed(self, index):
        """Handle target selection change."""
        is_specific = self.target_combo.currentData() == "specific"
        self.clip_selector_group.setVisible(is_specific)
    
    def _browse_file(self):
        """Open file browser to select a subtitle file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Subtitle File",
            "",
            subtitle_file_dialog_filter(),
        )
        
        if not file_path:
            return
        
        path = Path(file_path)
        try:
            self.loaded_captions = parse_subtitle_file(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Failed to Parse File",
                f"Could not parse subtitle file:\n{exc}"
            )
            return
        
        if not self.loaded_captions:
            QMessageBox.warning(
                self,
                "No Captions Found",
                "The subtitle file contains no valid captions."
            )
            return
        
        self.subtitle_path = path
        self.file_label.setText(path.name)
        self.file_label.setStyleSheet("")
        self.import_btn.setEnabled(True)
        
        # Update previews
        self._update_previews()
    
    def _update_previews(self):
        """Update the preview tabs with loaded captions."""
        # ── List preview ────
        self.captions_list.clear()
        for caption in self.loaded_captions:
            start = self._fmt_seconds(caption["start"])
            end = self._fmt_seconds(caption["end"])
            text = caption["text"][:60]  # Truncate for display
            item_text = f"[{start} → {end}] {text}"
            item = QListWidgetItem(item_text)
            self.captions_list.addItem(item)
        
        # ── Table preview ───
        self.captions_table.setRowCount(len(self.loaded_captions))
        for row, caption in enumerate(self.loaded_captions):
            start_item = QTableWidgetItem(self._fmt_seconds(caption["start"]))
            end_item = QTableWidgetItem(self._fmt_seconds(caption["end"]))
            text_item = QTableWidgetItem(caption["text"])
            
            # Make read-only
            for item in (start_item, end_item, text_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            self.captions_table.setItem(row, 0, start_item)
            self.captions_table.setItem(row, 1, end_item)
            self.captions_table.setItem(row, 2, text_item)
    
    @staticmethod
    def _fmt_seconds(seconds: float) -> str:
        """Format seconds to HH:MM:SS.ms string."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 100)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}.{ms:02d}"
        return f"{m}:{s:02d}.{ms:02d}"
    
    def get_import_settings(self) -> dict:
        """Return the current import settings."""
        return {
            "captions": self.loaded_captions,
            "subtitle_path": self.subtitle_path,
            "target": self.target_combo.currentData(),
            "clip_id": self.clip_combo.currentData() if self.target_combo.currentData() == "specific" else None,
            "offset": float(self.offset_spin.value()),
        }
