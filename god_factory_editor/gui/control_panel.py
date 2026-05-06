"""
Control Panel — comprehensive command center with all hotkey actions and quick controls.
Modern, organized, glowy aesthetic matching the app theme.
"""

from __future__ import annotations
from typing import Optional, Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QSpinBox, QComboBox,
    QGroupBox, QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from god_factory_editor.config import COLOURS


class ControlPanel(QDockWidget):
    """
    Dockable control panel with:
    - All hotkey actions as buttons
    - Quick effect controls (sliders, dropdowns)
    - Organized sections (File, Playback, Clip, Effects, etc.)
    - Modern glowy aesthetic
    """
    
    # Signals for actions
    action_triggered = Signal(str)  # Emits action name
    
    def __init__(self, parent=None):
        super().__init__("Control Panel", parent)
        self.setObjectName("ControlPanel")
        
        # Create main widget
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)
        
        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #0a0a0a;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #2d5a2d;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #3d7a3d;
            }
        """)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Build all control sections
        content_layout.addWidget(self._build_file_section())
        content_layout.addWidget(self._build_playback_section())
        content_layout.addWidget(self._build_clip_section())
        content_layout.addWidget(self._build_effects_section())
        content_layout.addWidget(self._build_detection_section())
        content_layout.addWidget(self._build_export_section())
        content_layout.addWidget(self._build_view_section())
        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        self.setWidget(main_widget)
        self.setMinimumWidth(280)
        
        # Apply glowy dark theme
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply glowy zombie aesthetic to the panel."""
        self.setStyleSheet(f"""
            QDockWidget {{
                background-color: #0a0a0a;
                color: {COLOURS['text_primary']};
                border: 1px solid {COLOURS['accent_gold']};
                border-radius: 4px;
            }}
            QDockWidget::title {{
                background-color: #0a0a0a;
                color: {COLOURS['text_primary']};
                padding: 4px;
                font-weight: bold;
                border-bottom: 1px solid {COLOURS['accent_gold']};
            }}
        """)
    
    def _create_section(self, title: str) -> tuple[QGroupBox, QVBoxLayout]:
        """Create a glowy section with title."""
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Glowy style
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOURS['accent_gold']};
                border: 1px solid {COLOURS['accent_gold']};
                border-radius: 4px;
                margin-top: 6px;
                padding-top: 6px;
                background-color: rgba(10, 10, 10, 0.8);
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
                color: {COLOURS['accent_gold']};
                font-weight: bold;
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
        """)
        
        return group, layout
    
    def _create_button(self, text: str, action_name: str, tooltip: str = "") -> QPushButton:
        """Create a glowy button."""
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.action_triggered.emit(action_name))
        
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #1a2a1a;
                color: {COLOURS['accent_gold']};
                border: 1px solid {COLOURS['accent_gold']};
                border-radius: 3px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 9px;
            }}
            QPushButton:hover {{
                background-color: #2d4a2d;
                border: 1px solid {COLOURS['text_primary']};
                color: {COLOURS['text_primary']};
            }}
            QPushButton:pressed {{
                background-color: #1a3a1a;
                border: 2px solid {COLOURS['text_primary']};
            }}
        """)
        
        return btn
    
    def _create_slider(self, min_val: int, max_val: int, default: int = 0) -> QSlider:
        """Create a glowy slider."""
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background-color: #1a1a1a;
                height: 4px;
                border-radius: 2px;
                border: 1px solid {COLOURS['accent_gold']};
            }}
            QSlider::handle:horizontal {{
                background-color: {COLOURS['accent_gold']};
                width: 12px;
                margin: -4px 0px;
                border-radius: 6px;
                border: 1px solid {COLOURS['text_primary']};
            }}
            QSlider::handle:horizontal:hover {{
                background-color: {COLOURS['text_primary']};
            }}
        """)
        return slider
    
    def _create_spinbox(self, min_val: int, max_val: int, default: int = 0) -> QSpinBox:
        """Create a glowy spinbox."""
        spin = QSpinBox()
        spin.setMinimum(min_val)
        spin.setMaximum(max_val)
        spin.setValue(default)
        spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: #1a1a1a;
                color: {COLOURS['accent_gold']};
                border: 1px solid {COLOURS['accent_gold']};
                border-radius: 3px;
                padding: 2px 4px;
                font-weight: bold;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 16px;
                background-color: #2a2a2a;
                border: 1px solid {COLOURS['accent_gold']};
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: #2d5a2d;
            }}
        """)
        return spin
    
    def _create_combo(self, items: list[str]) -> QComboBox:
        """Create a glowy combo box."""
        combo = QComboBox()
        combo.addItems(items)
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #1a1a1a;
                color: {COLOURS['accent_gold']};
                border: 1px solid {COLOURS['accent_gold']};
                border-radius: 3px;
                padding: 2px 4px;
                font-weight: bold;
            }}
            QComboBox::drop-down {{
                border: 1px solid {COLOURS['accent_gold']};
                border-radius: 2px;
                width: 16px;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a1a;
                color: {COLOURS['accent_gold']};
                selection-background-color: #2d5a2d;
                border: 1px solid {COLOURS['accent_gold']};
                border-radius: 3px;
            }}
        """)
        return combo
    
    def _build_file_section(self) -> QGroupBox:
        """FILE: Open, Save, Project, Settings, Quit."""
        group, layout = self._create_section("FILE")
        
        layout.addWidget(self._create_button("Open Video", "open_video", "Ctrl+O"))
        layout.addWidget(self._create_button("Open Project", "open_project", "Ctrl+Shift+O"))
        layout.addWidget(self._create_button("Import Subtitles", "import_subtitles", "Ctrl+Shift+T"))
        layout.addWidget(self._create_button("Save Project", "save_project", "Ctrl+S"))
        layout.addWidget(self._create_button("Save As...", "save_project_as", "Ctrl+Shift+S"))
        layout.addWidget(self._create_button("Settings", "settings", "Ctrl+,"))
        
        return group
    
    def _build_playback_section(self) -> QGroupBox:
        """PLAYBACK: Play/Pause, Seek, Volume."""
        group, layout = self._create_section("PLAYBACK")
        
        # Play/Pause and seek buttons
        row1 = QHBoxLayout()
        row1.addWidget(self._create_button("Play/Pause", "play_pause", "Space"))
        row1.addWidget(self._create_button("Stop", "stop_playback", ""))
        layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        row2.addWidget(self._create_button("◄◄ -30s", "seek_back_large", "Shift+Left"))
        row2.addWidget(self._create_button("◄ -5s", "seek_back", "Left"))
        layout.addLayout(row2)
        
        row3 = QHBoxLayout()
        row3.addWidget(self._create_button("► +5s", "seek_forward", "Right"))
        row3.addWidget(self._create_button("►► +30s", "seek_forward_large", "Shift+Right"))
        layout.addLayout(row3)
        
        # Volume control
        layout.addWidget(QLabel("Volume:"))
        vol_layout = QHBoxLayout()
        vol_slider = self._create_slider(0, 100, 80)
        vol_label = QLabel("80%")
        vol_label.setStyleSheet(f"color: {COLOURS['accent_gold']}; font-weight: bold; min-width: 35px;")
        vol_slider.valueChanged.connect(lambda v: vol_label.setText(f"{v}%"))
        vol_slider.valueChanged.connect(lambda v: self.action_triggered.emit(f"set_volume:{v}"))
        vol_layout.addWidget(vol_slider, 1)
        vol_layout.addWidget(vol_label)
        layout.addLayout(vol_layout)
        
        return group
    
    def _build_clip_section(self) -> QGroupBox:
        """CLIP: Mark In/Out, Split, Delete, Rename, Loop, Edit."""
        group, layout = self._create_section("CLIP OPERATIONS")
        
        row1 = QHBoxLayout()
        row1.addWidget(self._create_button("Mark In", "mark_in", "I"))
        row1.addWidget(self._create_button("Mark Out", "mark_out", "O"))
        layout.addLayout(row1)
        
        layout.addWidget(self._create_button("Split at Playhead", "split", "S"))
        layout.addWidget(self._create_button("Delete Selected", "delete_clip", "Delete"))
        layout.addWidget(self._create_button("Rename", "rename_clip", "F2"))
        layout.addWidget(self._create_button("Loop Clip (A-B)", "toggle_loop", "L"))
        layout.addWidget(self._create_button("Edit Effects", "edit_effects", "E"))
        layout.addWidget(self._create_button("Merge Clips", "merge_clips", ""))
        
        return group
    
    def _build_effects_section(self) -> QGroupBox:
        """EFFECTS: Speed, Transitions, SFX, Audio, Picture quick controls."""
        group, layout = self._create_section("QUICK EFFECTS")
        
        # Speed preset
        layout.addWidget(QLabel("Speed Multiplier:"))
        speed_layout = QHBoxLayout()
        speed_combo = self._create_combo(["0.25x", "0.5x", "0.75x", "1.0x", "1.5x", "2.0x", "3.0x", "4.0x"])
        speed_combo.setCurrentText("1.0x")
        speed_combo.currentTextChanged.connect(lambda v: self.action_triggered.emit(f"set_speed:{v}"))
        speed_layout.addWidget(speed_combo)
        layout.addLayout(speed_layout)
        
        # Transition preset
        layout.addWidget(QLabel("Transition Type:"))
        trans_layout = QHBoxLayout()
        trans_combo = self._create_combo(["None", "Fade", "Dissolve", "Wipe Left", "Wipe Right", "Zoom"])
        trans_combo.currentTextChanged.connect(lambda v: self.action_triggered.emit(f"set_transition:{v}"))
        trans_layout.addWidget(trans_combo)
        layout.addLayout(trans_layout)
        
        # Audio enhancement presets
        layout.addWidget(QLabel("Audio Preset:"))
        audio_layout = QHBoxLayout()
        audio_combo = self._create_combo(["Normal", "Voice Boost", "Game Ducking", "Normalize", "Denoise"])
        audio_combo.currentTextChanged.connect(lambda v: self.action_triggered.emit(f"set_audio_preset:{v}"))
        audio_layout.addWidget(audio_combo)
        layout.addLayout(audio_layout)
        
        # Quick picture adjustments
        layout.addWidget(QLabel("Brightness:"))
        bright_slider = self._create_slider(-50, 50, 0)
        bright_label = QLabel("0%")
        bright_label.setStyleSheet(f"color: {COLOURS['accent_gold']}; font-weight: bold; min-width: 35px;")
        bright_slider.valueChanged.connect(lambda v: bright_label.setText(f"{v:+d}%"))
        bright_slider.valueChanged.connect(lambda v: self.action_triggered.emit(f"set_brightness:{v}"))
        bright_row = QHBoxLayout()
        bright_row.addWidget(bright_slider, 1)
        bright_row.addWidget(bright_label)
        layout.addLayout(bright_row)
        
        layout.addWidget(QLabel("Contrast:"))
        contrast_slider = self._create_slider(50, 200, 100)
        contrast_label = QLabel("100%")
        contrast_label.setStyleSheet(f"color: {COLOURS['accent_gold']}; font-weight: bold; min-width: 35px;")
        contrast_slider.valueChanged.connect(lambda v: contrast_label.setText(f"{v}%"))
        contrast_slider.valueChanged.connect(lambda v: self.action_triggered.emit(f"set_contrast:{v}"))
        contrast_row = QHBoxLayout()
        contrast_row.addWidget(contrast_slider, 1)
        contrast_row.addWidget(contrast_label)
        layout.addLayout(contrast_row)
        
        layout.addWidget(QLabel("Saturation:"))
        sat_slider = self._create_slider(0, 300, 100)
        sat_label = QLabel("100%")
        sat_label.setStyleSheet(f"color: {COLOURS['accent_gold']}; font-weight: bold; min-width: 35px;")
        sat_slider.valueChanged.connect(lambda v: sat_label.setText(f"{v}%"))
        sat_slider.valueChanged.connect(lambda v: self.action_triggered.emit(f"set_saturation:{v}"))
        sat_row = QHBoxLayout()
        sat_row.addWidget(sat_slider, 1)
        sat_row.addWidget(sat_label)
        layout.addLayout(sat_row)
        
        return group
    
    def _build_detection_section(self) -> QGroupBox:
        """DETECTION: Scene detection, Auto-cut."""
        group, layout = self._create_section("DETECTION & AUTO-EDIT")
        
        layout.addWidget(self._create_button("Auto-Detect Scenes", "auto_detect", "Ctrl+D"))
        layout.addWidget(self._create_button("Auto-Cut Boring Parts", "auto_cut_boring", "Ctrl+Shift+D"))
        layout.addWidget(self._create_button("Auto-Suggest Transitions", "auto_suggest_transitions", ""))
        layout.addWidget(self._create_button("Auto-Suggest SFX", "auto_suggest_sfx", ""))
        layout.addWidget(self._create_button("Auto-Edit Settings...", "open_auto_edit_settings", ""))
        
        return group
    
    def _build_export_section(self) -> QGroupBox:
        """EXPORT: Export selected, all, single video."""
        group, layout = self._create_section("EXPORT")
        
        layout.addWidget(self._create_button("Export Selected", "export_selected", "Ctrl+E"))
        layout.addWidget(self._create_button("Export All Clips", "export_all", "Ctrl+Shift+E"))
        layout.addWidget(self._create_button("Export as Single Video", "export_single", "Ctrl+Shift+M"))
        
        return group
    
    def _build_view_section(self) -> QGroupBox:
        """VIEW: Proxy, Timeline, Help, Undo/Redo."""
        group, layout = self._create_section("VIEW & TOOLS")
        
        layout.addWidget(self._create_button("Toggle Proxy Mode", "toggle_proxy", "Ctrl+P"))
        layout.addWidget(self._create_button("Fit Timeline", "fit_timeline", "F"))
        
        row_undo = QHBoxLayout()
        row_undo.addWidget(self._create_button("Undo", "undo", "Ctrl+Z"))
        row_undo.addWidget(self._create_button("Redo", "redo", "Ctrl+Y"))
        layout.addLayout(row_undo)
        
        layout.addWidget(self._create_button("Help", "help", "F1"))
        
        return group
