"""
MainWindow — the central hub of The God Factory Video Editor.
Wires together every subsystem:
  VideoPlayer ↔ ClipManager ↔ TimelineWidget ↔ ClipListWidget
  StreamManager, ProxyManager, ExportEngine, SceneDetector
"""

from __future__ import annotations

import time
import random
import tempfile
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, QTimer, QSettings, QSize
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStatusBar, QToolBar, QFileDialog, QMessageBox,
    QInputDialog, QScrollArea, QDialog,
)
from PySide6.QtGui import QAction, QKeySequence, QDragEnterEvent, QDropEvent

from god_factory_editor.config import (
    APP_NAME, APP_VERSION, PROJECT_EXTENSION, settings, COLOURS, SOCIAL_LINKS,
)
from god_factory_editor.models.project_data import ProjectData
from god_factory_editor.models.clip import Clip
from god_factory_editor.core.stream_manager import StreamManager
from god_factory_editor.core.clip_manager import ClipManager
from god_factory_editor.core.proxy_manager import ProxyManager
from god_factory_editor.core.export_engine import ExportEngine
from god_factory_editor.core.scene_detector import SceneDetector
from god_factory_editor.gui.video_player import VideoPlayer
from god_factory_editor.gui.timeline_widget import TimelineWidget
from god_factory_editor.gui.clip_list_widget import ClipListWidget
from god_factory_editor.gui.control_panel import ControlPanel
from god_factory_editor.gui.export_dialog import ExportDialog
from god_factory_editor.gui.settings_dialog import SettingsDialog
from god_factory_editor.gui.help_window import HelpWindow, get_help_tip_pool
from god_factory_editor.gui.dialogs.clip_effects_dialog import ClipEffectsDialog
from god_factory_editor.gui.dialogs.auto_edit_dialog import AutoEditDialog
from god_factory_editor.gui.dialogs.error_handler import (
    show_error, show_warning, show_info, ask_yes_no,
)
from god_factory_editor.gui.dialogs.progress_dialog import ProgressDialog
from god_factory_editor.gui.dialogs.automation_wizard_dialog import AutomationWizardDialog
from god_factory_editor.utils.logger import log
from god_factory_editor.utils.file_utils import (
    is_video_file,
    is_external_project_file,
    video_file_dialog_filter,
    external_project_file_dialog_filter,
)
from god_factory_editor.utils.ffmpeg_wrapper import ffmpeg
from god_factory_editor.config import TEMP_DIR


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1280, 720)
        self.setAcceptDrops(True)

        # Subsystems
        self._stream_manager = StreamManager()
        self._clip_manager   = ClipManager()
        self._proxy_manager  = ProxyManager()
        self._export_engine  = ExportEngine()
        self._scene_detector: Optional[SceneDetector] = None  # created on demand

        # State
        self._project:       Optional[ProjectData] = None
        self._project_path:  Optional[Path]        = None
        self._video_path:    Optional[Path]         = None
        self._mark_in_time:  Optional[float]        = None
        self._unsaved:       bool                   = False
        self._autosave_path: Optional[Path]         = None
        self._analysis_start: float                 = 0.0
        self._analysis_end: Optional[float]         = None
        self._excluded_ranges: list[tuple[float, float]] = []
        self._preview_file: Optional[Path]          = None
        self._preview_restore_pos: float            = 0.0

        # Build UI
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_control_panel()
        self._build_status_bar()

        # Auto-save timer
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        interval_ms = settings.get("auto_save_interval", 30) * 1000
        self._autosave_timer.start(interval_ms)

        # Connect internal signals
        self._connect_signals()

        # Restore window geometry
        self._restore_geometry()

        # Check for an auto-save recovery file
        QTimer.singleShot(200, self._check_recovery)
        QTimer.singleShot(1200, self._run_startup_maintenance)
        # First-run wizard — show once, never again
        if not settings.get("first_run_done", False):
            QTimer.singleShot(600, self._show_first_run_wizard)

    # ── Menu ──────────────────────────────────────────────────────────────────
    def _build_menu(self):
        kb = settings.get("shortcuts", {})
        mb = self.menuBar()

        # ── File ──
        file_menu = mb.addMenu("File")

        self._act_open = QAction("Open Video…", self)
        self._act_open.setShortcut(kb.get("open", "Ctrl+O"))
        self._act_open.triggered.connect(self.open_video)
        file_menu.addAction(self._act_open)

        self._act_open_project = QAction("Open Project (.gfve)…", self)
        self._act_open_project.setShortcut("Ctrl+Shift+O")
        self._act_open_project.triggered.connect(self.open_project)
        file_menu.addAction(self._act_open_project)

        self._act_import_external_project = QAction("Import External Editor Project…", self)
        self._act_import_external_project.setShortcut(kb.get("import_external_project", "Ctrl+Alt+O"))
        self._act_import_external_project.triggered.connect(self.import_external_project)
        file_menu.addAction(self._act_import_external_project)

        self._act_import_subtitles = QAction("Import Subtitles…", self)
        self._act_import_subtitles.setShortcut("Ctrl+Shift+T")
        self._act_import_subtitles.triggered.connect(self._import_subtitles)
        file_menu.addAction(self._act_import_subtitles)

        file_menu.addSeparator()

        # ── Recent Files submenu (actually populated from settings) ──
        self._recent_menu = file_menu.addMenu("Open Recent")
        self._rebuild_recent_menu()

        file_menu.addSeparator()

        self._act_save = QAction("Save Project", self)
        self._act_save.setShortcut(kb.get("save", "Ctrl+S"))
        self._act_save.triggered.connect(self.save_project)
        file_menu.addAction(self._act_save)

        self._act_save_as = QAction("Save Project As…", self)
        self._act_save_as.setShortcut("Ctrl+Shift+S")
        self._act_save_as.triggered.connect(self.save_project_as)
        file_menu.addAction(self._act_save_as)

        file_menu.addSeparator()

        act_settings = QAction("Settings…", self)
        act_settings.setShortcut("Ctrl+,")
        act_settings.triggered.connect(self.open_settings)
        file_menu.addAction(act_settings)

        file_menu.addSeparator()

        act_quit = QAction("Quit", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # ── Edit ──
        edit_menu = mb.addMenu("Edit")

        self._act_undo = QAction("Undo", self)
        self._act_undo.setShortcut(kb.get("undo", "Ctrl+Z"))
        self._act_undo.triggered.connect(self._clip_manager.undo)
        edit_menu.addAction(self._act_undo)

        self._act_redo = QAction("Redo", self)
        self._act_redo.setShortcut(kb.get("redo", "Ctrl+Y"))
        self._act_redo.triggered.connect(self._clip_manager.redo)
        edit_menu.addAction(self._act_redo)

        # ── Clip ──
        clip_menu = mb.addMenu("Clip")

        self._act_mark_in = QAction("Mark In (Clip Start)", self)
        self._act_mark_in.setShortcut(kb.get("mark_in", "I"))
        self._act_mark_in.triggered.connect(self._mark_in)
        clip_menu.addAction(self._act_mark_in)

        self._act_mark_out = QAction("Mark Out (Clip End)", self)
        self._act_mark_out.setShortcut(kb.get("mark_out", "O"))
        self._act_mark_out.triggered.connect(self._mark_out)
        clip_menu.addAction(self._act_mark_out)

        self._act_split = QAction("Split at Playhead", self)
        self._act_split.setShortcut(kb.get("split", "S"))
        self._act_split.triggered.connect(self._split_clip)
        clip_menu.addAction(self._act_split)

        self._act_delete = QAction("Delete Selected Clip", self)
        self._act_delete.setShortcut(kb.get("delete", "Delete"))
        self._act_delete.triggered.connect(self._delete_selected_clip)
        clip_menu.addAction(self._act_delete)

        self._act_rename = QAction("Rename Clip", self)
        self._act_rename.setShortcut(kb.get("rename", "F2"))
        self._act_rename.triggered.connect(self._rename_selected_clip)
        clip_menu.addAction(self._act_rename)

        self._act_loop = QAction("Loop Clip (A-B)", self)
        self._act_loop.setShortcut(kb.get("loop_clip", "L"))
        self._act_loop.triggered.connect(self._toggle_loop)
        clip_menu.addAction(self._act_loop)

        # ── Detection ──
        det_menu = mb.addMenu("Detection")

        self._act_autodetect = QAction("Auto-Detect Scenes", self)
        self._act_autodetect.setShortcut(kb.get("auto_detect", "Ctrl+D"))
        self._act_autodetect.triggered.connect(self._run_auto_detect)
        det_menu.addAction(self._act_autodetect)

        act_auto_cut_boring = QAction("Auto-Cut Boring Parts…", self)
        act_auto_cut_boring.setShortcut("Ctrl+Shift+D")
        act_auto_cut_boring.triggered.connect(self._auto_cut_boring_parts)
        det_menu.addAction(act_auto_cut_boring)

        # ── Automation ──
        auto_menu = mb.addMenu("Automation")

        self._act_automation_wizard = QAction("Automation Wizard…", self)
        self._act_automation_wizard.setShortcut(kb.get("automation_wizard", "Ctrl+Alt+W"))
        self._act_automation_wizard.triggered.connect(self._open_automation_wizard)
        auto_menu.addAction(self._act_automation_wizard)

        self._act_decibel_scan = QAction("Run Decibel / Loudness Scan", self)
        self._act_decibel_scan.setShortcut(kb.get("decibel_scan", "Ctrl+Alt+L"))
        self._act_decibel_scan.triggered.connect(self._run_decibel_scan)
        auto_menu.addAction(self._act_decibel_scan)

        auto_menu.addSeparator()

        self._act_work_start = QAction("Set Work Start At Playhead", self)
        self._act_work_start.setShortcut(kb.get("set_work_start", "Ctrl+Alt+1"))
        self._act_work_start.triggered.connect(self._set_work_start_here)
        auto_menu.addAction(self._act_work_start)

        self._act_work_end = QAction("Set Work End At Playhead", self)
        self._act_work_end.setShortcut(kb.get("set_work_end", "Ctrl+Alt+2"))
        self._act_work_end.triggered.connect(self._set_work_end_here)
        auto_menu.addAction(self._act_work_end)

        self._act_work_clear = QAction("Clear Work Area + Excluded Zones", self)
        self._act_work_clear.setShortcut(kb.get("clear_work_area", "Ctrl+Alt+0"))
        self._act_work_clear.triggered.connect(self._clear_work_area)
        auto_menu.addAction(self._act_work_clear)

        self._act_exclude_selected = QAction("Exclude Selected Clips From Automation", self)
        self._act_exclude_selected.setShortcut(kb.get("exclude_selected", "Ctrl+Alt+X"))
        self._act_exclude_selected.triggered.connect(self._exclude_selected_clips_from_automation)
        auto_menu.addAction(self._act_exclude_selected)

        # ── View ──
        view_menu = mb.addMenu("View")

        self._act_proxy = QAction("Toggle Proxy Mode", self)
        self._act_proxy.setShortcut(kb.get("toggle_proxy", "Ctrl+P"))
        self._act_proxy.setCheckable(True)
        self._act_proxy.setChecked(settings.get("proxy_enabled", True))
        # triggered(checked) passes the new checked bool directly — no ambiguity
        self._act_proxy.triggered.connect(self._toggle_proxy)
        view_menu.addAction(self._act_proxy)

        self._act_theme = QAction("Toggle Light/Dark Theme", self)
        self._act_theme.setShortcut("Ctrl+T")
        self._act_theme.setCheckable(True)
        self._act_theme.setChecked(settings.get("theme", "dark") == "light")
        self._act_theme.triggered.connect(
            lambda checked: self._apply_theme("light" if checked else "dark")
        )
        view_menu.addAction(self._act_theme)

        self._act_fit = QAction("Fit Timeline to Window", self)
        self._act_fit.setShortcut(kb.get("fit_timeline", "F"))
        self._act_fit.triggered.connect(lambda: self._timeline.fit_to_window())
        view_menu.addAction(self._act_fit)

        # ── Export ──
        export_menu = mb.addMenu("Export")

        self._act_export_sel = QAction("Export Selected Clips…", self)
        self._act_export_sel.setShortcut(kb.get("export_selected", "Ctrl+E"))
        self._act_export_sel.triggered.connect(self._export_selected)
        export_menu.addAction(self._act_export_sel)

        self._act_export_all = QAction("Export All Clips…", self)
        self._act_export_all.setShortcut(kb.get("export_all", "Ctrl+Shift+E"))
        self._act_export_all.triggered.connect(self._export_all)
        export_menu.addAction(self._act_export_all)

        # ── Effects ──
        fx_menu = mb.addMenu("Effects")

        act_clip_effects = QAction("Edit Clip Effects…", self)
        act_clip_effects.setShortcut("E")
        act_clip_effects.triggered.connect(self._open_clip_effects)
        fx_menu.addAction(act_clip_effects)

        act_preview_effects = QAction("Preview Selected Clip With Effects…", self)
        act_preview_effects.setShortcut(kb.get("preview_effects", "Ctrl+Shift+P"))
        act_preview_effects.triggered.connect(self._preview_selected_with_effects)
        fx_menu.addAction(act_preview_effects)

        act_return_source = QAction("Return To Source Playback", self)
        act_return_source.triggered.connect(self._return_to_source_preview)
        fx_menu.addAction(act_return_source)

        act_preview_sequence = QAction("Preview All Clips as Sequence…", self)
        act_preview_sequence.setShortcut(kb.get("preview_sequence", "Ctrl+Shift+A"))
        act_preview_sequence.triggered.connect(self._preview_clip_sequence)
        fx_menu.addAction(act_preview_sequence)

        fx_menu.addSeparator()

        act_auto_trans = QAction("Auto-Suggest Transitions…", self)
        act_auto_trans.triggered.connect(self._auto_suggest_transitions)
        fx_menu.addAction(act_auto_trans)

        act_auto_sfx = QAction("Auto-Suggest Sound Effects…", self)
        act_auto_sfx.triggered.connect(self._auto_suggest_sfx)
        fx_menu.addAction(act_auto_sfx)

        fx_menu.addSeparator()

        act_export_single = QAction("Export as Single Video (with Transitions)…", self)
        act_export_single.setShortcut("Ctrl+Shift+M")
        act_export_single.triggered.connect(self._export_as_single)
        fx_menu.addAction(act_export_single)

        # ── Help ──
        help_menu = mb.addMenu("Help")

        self._act_help = QAction("Open Help", self)
        self._act_help.setShortcut(kb.get("help", "F1"))
        self._act_help.triggered.connect(lambda: self._show_help("welcome"))
        help_menu.addAction(self._act_help)

        help_menu.addSeparator()

        act_about = QAction(f"About {APP_NAME}", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

        # ── Community / Promo menu ─────────────────────────────────────────
        community_menu = mb.addMenu("Community")

        act_youtube = QAction("YouTube Channel", self)
        act_youtube.setToolTip("Watch and subscribe on YouTube")
        act_youtube.triggered.connect(lambda: self._open_social("youtube"))
        community_menu.addAction(act_youtube)

        act_discord = QAction("Discord Server", self)
        act_discord.setToolTip("Join the Discord community")
        act_discord.triggered.connect(lambda: self._open_social("discord"))
        community_menu.addAction(act_discord)

        community_menu.addSeparator()

        act_paypal = QAction("Donate via PayPal", self)
        act_paypal.setToolTip("Support development with a PayPal donation")
        act_paypal.triggered.connect(lambda: self._open_social("paypal"))
        community_menu.addAction(act_paypal)

        act_cashapp = QAction("Donate via Cash App", self)
        act_cashapp.setToolTip("Support development via Cash App")
        act_cashapp.triggered.connect(lambda: self._open_social("cashapp"))
        community_menu.addAction(act_cashapp)

    # ── Toolbar ───────────────────────────────────────────────────────────────
    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setObjectName("MainToolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))
        self.addToolBar(tb)

        tb.addAction(self._act_open)
        tb.addAction(self._act_save)
        tb.addSeparator()
        tb.addAction(self._act_mark_in)
        tb.addAction(self._act_mark_out)
        tb.addAction(self._act_split)
        tb.addSeparator()
        tb.addAction(self._act_autodetect)
        tb.addSeparator()
        tb.addAction(self._act_export_sel)
        tb.addSeparator()
        tb.addAction(self._act_undo)
        tb.addAction(self._act_redo)
        tb.addSeparator()
        tb.addAction(self._act_proxy)
        tb.addSeparator()
        tb.addAction(self._act_help)

    # ── Central widget ────────────────────────────────────────────────────────
    def _build_central(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Workflow guide banner — always visible, dismissible
        self._workflow_banner = QLabel(
            "  HOW TO CLIP:  "
            "① Play video (Space)  "
            "② Press I at the start of a good segment  "
            "③ Press O at the end  "
            "④ Name it → clip appears in the list  "
            "⑤ Tick clips → Export Selected (Ctrl+E)  "
            "  |  Double-click any clip to jump there  "
            "  |  Delete removes the marker, not the source  "
            "  [×]"
        )
        self._workflow_banner.setObjectName("workflowBanner")
        self._workflow_banner.setStyleSheet(
            "QLabel#workflowBanner {"
            "  background: #1a2e1a;"
            "  color: #b8e0b0;"
            "  border-bottom: 1px solid #3d6e3d;"
            "  padding: 4px 12px;"
            "  font-size: 11px;"
            "}"
        )
        self._workflow_banner.setCursor(Qt.PointingHandCursor)
        self._workflow_banner.mousePressEvent = lambda e: self._workflow_banner.hide()
        outer.addWidget(self._workflow_banner)

        # Preview-mode banner — visible only when playing rendered previews.
        self._preview_banner = QWidget()
        self._preview_banner.setObjectName("previewBanner")
        self._preview_banner.setStyleSheet(
            "QWidget#previewBanner {"
            "  background: #3a2414;"
            "  border-bottom: 1px solid #8b5a2b;"
            "}"
            "QWidget#previewBanner QLabel {"
            "  color: #ffd9a1;"
            "  font-size: 11px;"
            "}"
            "QWidget#previewBanner QPushButton {"
            "  background: #8b5a2b;"
            "  color: #ffffff;"
            "  border: 1px solid #b97a3f;"
            "  border-radius: 4px;"
            "  padding: 2px 10px;"
            "}"
            "QWidget#previewBanner QPushButton:hover {"
            "  background: #a3682f;"
            "}"
        )
        preview_row = QHBoxLayout(self._preview_banner)
        preview_row.setContentsMargins(10, 3, 10, 3)
        preview_row.setSpacing(10)
        self._preview_banner_label = QLabel(
            "Preview mode is active. Press Esc or click Return To Timeline."
        )
        preview_row.addWidget(self._preview_banner_label)
        preview_row.addStretch()
        self._preview_banner_btn = QPushButton("Return To Timeline")
        self._preview_banner_btn.clicked.connect(self._return_to_source_preview)
        preview_row.addWidget(self._preview_banner_btn)
        self._preview_banner.hide()
        outer.addWidget(self._preview_banner)

        # Top split: player (left) + clip list (right)
        top_split = QSplitter(Qt.Horizontal)

        # Video player
        self._player = VideoPlayer()
        self._player.setMinimumWidth(640)
        top_split.addWidget(self._player)

        # Clip list
        self._clip_list = ClipListWidget(self._clip_manager)
        self._clip_list.setMinimumWidth(320)
        top_split.addWidget(self._clip_list)
        top_split.setStretchFactor(0, 3)
        top_split.setStretchFactor(1, 1)

        outer.addWidget(top_split, stretch=4)

        # Timeline (bottom, full width)
        self._timeline = TimelineWidget(self._clip_manager)
        self._timeline.setMinimumHeight(100)
        self._timeline.setMaximumHeight(180)
        self._timeline_scroll = QScrollArea()
        self._timeline_scroll.setWidget(self._timeline)
        self._timeline_scroll.setWidgetResizable(False)
        self._timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._timeline_scroll.setMinimumHeight(118)
        self._timeline_scroll.setMaximumHeight(198)
        outer.addWidget(self._timeline_scroll, stretch=1)

    # ── Status bar ────────────────────────────────────────────────────────────
    def _build_status_bar(self):
        sb = self.statusBar()
        self._sb_tip      = QLabel("Tip feed initializing…")
        self._sb_tip.setStyleSheet(
            "color:#a7dba0; background:#132118; border:1px solid #2d4e34;"
            "border-radius:4px; padding:2px 8px;"
        )
        self._sb_file     = QLabel("No video loaded")
        self._sb_time     = QLabel("--:--:-- / --:--:--")
        self._sb_clips    = QLabel("0 clips")
        self._sb_proxy    = QLabel("")
        self._sb_mem      = QLabel("")

        for lbl in (self._sb_tip, self._sb_file, self._sb_time, self._sb_clips,
                    self._sb_proxy, self._sb_mem):
            sb.addPermanentWidget(lbl)
            sb.addPermanentWidget(_separator())

        # Memory/disk update timer
        self._sys_timer = QTimer(self)
        self._sys_timer.timeout.connect(self._update_sys_status)
        self._sys_timer.start(5000)

        # Rotating help tips (1.2s per word), pulled from all Help topics.
        self._tip_rng = random.Random()
        self._tip_last = ""
        self._tip_pool = get_help_tip_pool()
        self._tip_timer = QTimer(self)
        self._tip_timer.setSingleShot(True)
        self._tip_timer.timeout.connect(self._rotate_tip)
        self._rotate_tip()

    def _build_control_panel(self):
        """Create and setup the control panel dock widget."""
        self._control_panel = ControlPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._control_panel)
        self._control_panel.action_triggered.connect(self._on_control_panel_action)

    def _on_control_panel_action(self, action: str):
        """Handle actions from control panel."""
        # Parse action and parameters
        if ":" in action:
            action_name, param = action.split(":", 1)
        else:
            action_name = action
            param = None
        
        # ── FILE OPERATIONS ───────────────────────────────────────────────────
        if action_name == "open_video":
            self.open_video()
        elif action_name == "open_project":
            self.open_project()
        elif action_name == "import_external_project":
            self.import_external_project()
        elif action_name == "import_subtitles":
            self._import_subtitles()
        elif action_name == "save_project":
            self.save_project()
        elif action_name == "save_project_as":
            self.save_project_as()
        elif action_name == "settings":
            self.open_settings()
        
        # ── PLAYBACK CONTROL ──────────────────────────────────────────────────
        elif action_name == "play_pause":
            self._player.toggle_playback()
        elif action_name == "stop_playback":
            self._player.stop()
        elif action_name == "seek_back":
            step = settings.get("seek_step_small", 5)
            self._player.seek_relative(-step)
        elif action_name == "seek_back_large":
            step = settings.get("seek_step_large", 30)
            self._player.seek_relative(-step)
        elif action_name == "seek_forward":
            step = settings.get("seek_step_small", 5)
            self._player.seek_relative(step)
        elif action_name == "seek_forward_large":
            step = settings.get("seek_step_large", 30)
            self._player.seek_relative(step)
        elif action_name == "set_volume" and param:
            try:
                volume = int(param)
                self._player.set_volume(volume / 100.0)
            except ValueError:
                pass
        
        # ── CLIP OPERATIONS ───────────────────────────────────────────────────
        elif action_name == "mark_in":
            self._mark_in()
        elif action_name == "mark_out":
            self._mark_out()
        elif action_name == "split":
            self._split_clip()
        elif action_name == "delete_clip":
            self._delete_selected_clip()
        elif action_name == "rename_clip":
            self._rename_selected_clip()
        elif action_name == "toggle_loop":
            self._toggle_loop()
        elif action_name == "edit_effects":
            self._open_clip_effects()
        elif action_name == "preview_effects":
            self._preview_selected_with_effects()
        elif action_name == "return_source_preview":
            self._return_to_source_preview()
        elif action_name == "merge_clips":
            self._merge_clips()
        
        # ── EFFECTS (QUICK CONTROLS) ──────────────────────────────────────────
        elif action_name == "set_speed" and param:
            sel_ids = list(self._clip_manager.selected_clip_ids)
            clip = self._clip_manager.get_clip(sel_ids[0]) if sel_ids else None
            if clip:
                try:
                    speed = float(param.rstrip('x'))
                    clip.speed = speed
                    self._clip_manager.update_clip(clip.id)
                    self._clip_list.refresh()
                    self.statusBar().showMessage(
                        f"Speed set to {speed}x on '{clip.name}' — applies on export.", 4000
                    )
                except ValueError:
                    pass
            else:
                self.statusBar().showMessage("Select a clip first to set speed.", 3000)

        elif action_name == "set_transition" and param:
            sel_ids = list(self._clip_manager.selected_clip_ids)
            clip = self._clip_manager.get_clip(sel_ids[0]) if sel_ids else None
            if clip:
                trans_map = {
                    "None": "none",
                    "Fade": "fade",
                    "Dissolve": "dissolve",
                    "Wipe Left": "wipeleft",
                    "Wipe Right": "wiperight",
                    "Zoom": "zoom",
                }
                clip.transition_out = trans_map.get(param, "none")
                self._clip_manager.update_clip(clip.id)
                self._clip_list.refresh()
                self.statusBar().showMessage(
                    f"Transition '{param}' set on '{clip.name}' — applies when exporting as single video.", 4000
                )
            else:
                self.statusBar().showMessage("Select a clip first to set transition.", 3000)

        elif action_name == "set_audio_preset" and param:
            sel_ids = list(self._clip_manager.selected_clip_ids)
            clip = self._clip_manager.get_clip(sel_ids[0]) if sel_ids else None
            if clip:
                preset_map = {
                    "Normal": {},
                    "Voice Boost": {"audio_voice_boost": 6.0},
                    "Game Ducking": {"audio_game_duck": 6.0},
                    "Normalize": {"audio_normalize": True},
                    "Denoise": {"audio_denoise": True},
                }
                if param in preset_map:
                    for key, val in preset_map[param].items():
                        setattr(clip, key, val)
                    self._clip_manager.update_clip(clip.id)
                    self._clip_list.refresh()
                    if param != "Normal":
                        self.statusBar().showMessage(
                            f"Audio preset '{param}' applied to '{clip.name}' — use Preview Effects to hear it.", 5000
                        )
            else:
                self.statusBar().showMessage("Select a clip first to apply audio preset.", 3000)

        elif action_name == "set_brightness" and param:
            sel_ids = list(self._clip_manager.selected_clip_ids)
            clip = self._clip_manager.get_clip(sel_ids[0]) if sel_ids else None
            if clip:
                try:
                    clip.picture_brightness = int(param) / 100.0
                    self._clip_manager.update_clip(clip.id)
                    self._clip_list.refresh()
                    self.statusBar().showMessage(
                        f"Brightness {int(param):+d}% on '{clip.name}' — use Preview Effects to see it.", 4000
                    )
                except ValueError:
                    pass
            else:
                self.statusBar().showMessage("Select a clip first to adjust brightness.", 3000)

        elif action_name == "set_contrast" and param:
            sel_ids = list(self._clip_manager.selected_clip_ids)
            clip = self._clip_manager.get_clip(sel_ids[0]) if sel_ids else None
            if clip:
                try:
                    clip.picture_contrast = int(param) / 100.0
                    self._clip_manager.update_clip(clip.id)
                    self._clip_list.refresh()
                    self.statusBar().showMessage(
                        f"Contrast {int(param)}% on '{clip.name}' — use Preview Effects to see it.", 4000
                    )
                except ValueError:
                    pass
            else:
                self.statusBar().showMessage("Select a clip first to adjust contrast.", 3000)

        elif action_name == "set_saturation" and param:
            sel_ids = list(self._clip_manager.selected_clip_ids)
            clip = self._clip_manager.get_clip(sel_ids[0]) if sel_ids else None
            if clip:
                try:
                    clip.picture_saturation = int(param) / 100.0
                    self._clip_manager.update_clip(clip.id)
                    self._clip_list.refresh()
                    self.statusBar().showMessage(
                        f"Saturation {int(param)}% on '{clip.name}' — use Preview Effects to see it.", 4000
                    )
                except ValueError:
                    pass
            else:
                self.statusBar().showMessage("Select a clip first to adjust saturation.", 3000)

        # ── DETECTION & AUTO-EDIT ─────────────────────────────────────────────
        elif action_name == "auto_detect":
            self._run_auto_detect()
        elif action_name == "auto_cut_boring":
            self._auto_cut_boring_parts()
        elif action_name == "automation_wizard":
            self._open_automation_wizard()
        elif action_name == "decibel_scan":
            self._run_decibel_scan()
        elif action_name == "set_work_start":
            self._set_work_start_here()
        elif action_name == "set_work_end":
            self._set_work_end_here()
        elif action_name == "clear_work_area":
            self._clear_work_area()
        elif action_name == "exclude_selected":
            self._exclude_selected_clips_from_automation()
        elif action_name == "open_auto_edit_settings":
            self._auto_cut_boring_parts()  # Opens the Auto-Edit Settings dialog
        elif action_name == "auto_suggest_transitions":
            self._auto_suggest_transitions()
        elif action_name == "auto_suggest_sfx":
            self._auto_suggest_sfx()
        
        # ── EXPORT ────────────────────────────────────────────────────────────
        elif action_name == "export_selected":
            self._export_selected()
        elif action_name == "export_all":
            self._export_all()
        elif action_name == "export_single":
            self._export_as_single()
        
        # ── VIEW & TOOLS ──────────────────────────────────────────────────────
        elif action_name == "set_proxy" and param:
            # Emitted by the checkable proxy button with explicit "on"/"off" — no guessing
            enabled = (param == "on")
            self._act_proxy.setChecked(enabled)
            self._toggle_proxy(enabled)
        elif action_name == "set_theme" and param:
            self._apply_theme(param)
        elif action_name == "fit_timeline":
            self._timeline.fit_to_width()
        elif action_name == "undo":
            self._clip_manager.undo()
        elif action_name == "redo":
            self._clip_manager.redo()
        elif action_name == "help":
            self._show_help()

    # ── Signal wiring ─────────────────────────────────────────────────────────
    def _connect_signals(self):
        # Player → timeline playhead
        self._player.position_changed.connect(self._timeline.set_playhead)
        self._player.position_changed.connect(self._on_player_position)
        self._player.duration_changed.connect(self._timeline.set_duration)
        self._player.media_loaded.connect(self._on_media_loaded)
        self._player.media_error.connect(self._on_media_error)

        # Timeline → player seek
        self._timeline.seek_requested.connect(self._player.seek)

        # Timeline → clip selection
        self._timeline.clip_selected.connect(
            lambda cid: self._clip_list.select_clip(cid)
        )
        self._timeline.clip_double_clicked.connect(self._on_clip_double_click)

        # Clip list → player seek
        self._clip_list.clip_seek_requested.connect(self._player.seek)
        # rename_requested emits (clip_id, new_name) — use both args directly
        self._clip_list.rename_requested.connect(self._do_rename_clip_with_name)
        # delete_requested emits a list of ids
        self._clip_list.delete_requested.connect(self._do_delete_clips)

        # Effects panel signals from clip list
        self._clip_list.effects_split_requested.connect(self._split_clip)
        self._clip_list.effects_popout_requested.connect(self._open_clip_effects)

        # Clip manager → update counts
        self._clip_manager.clips_changed.connect(self._on_clips_changed)
        self._clip_manager.clips_changed.connect(lambda: self._mark_unsaved())

        # Proxy
        self._proxy_manager.proxy_ready.connect(self._on_proxy_ready)
        self._proxy_manager.proxy_failed.connect(self._on_proxy_failed)


    # ── Open / Save ───────────────────────────────────────────────────────────
    def open_video(self):
        if not self._confirm_discard():
            return
        last_dir = settings.get("last_open_dir", "")
        if last_dir and not Path(last_dir).exists():
            last_dir = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", last_dir,
            video_file_dialog_filter()
        )
        if path:
            log.info(f"Open Video dialog selected: {path}")
            settings.set("last_open_dir", str(Path(path).parent))
            self._load_video(Path(path))

    # ── Recent files ──────────────────────────────────────────────────────────
    def _rebuild_recent_menu(self):
        self._recent_menu.clear()
        recents = settings.get("recent_files", [])
        if not recents:
            empty_act = QAction("(none)", self)
            empty_act.setEnabled(False)
            self._recent_menu.addAction(empty_act)
            return
        for entry in recents[:15]:
            p = Path(entry)
            act = QAction(p.name, self)
            act.setToolTip(str(p))
            act.setData(str(p))
            act.triggered.connect(lambda checked=False, path=p: self._open_recent(path))
            self._recent_menu.addAction(act)
        self._recent_menu.addSeparator()
        clear_act = QAction("Clear Recent", self)
        clear_act.triggered.connect(self._clear_recent)
        self._recent_menu.addAction(clear_act)

    def _open_recent(self, path: Path):
        if not self._confirm_discard():
            return
        if not path.exists():
            from god_factory_editor.gui.dialogs.error_handler import show_warning
            show_warning(self, "File Not Found",
                         f"'{path.name}' no longer exists at:\n{path}")
            # Remove from recents
            recents = [r for r in settings.get("recent_files", []) if r != str(path)]
            settings.set("recent_files", recents)
            self._rebuild_recent_menu()
            return
        if path.suffix.lower() == PROJECT_EXTENSION:
            self._load_project(path)
        elif is_video_file(path):
            self._load_video(path)

    def _add_to_recent(self, path: Path):
        path_str = str(path)
        recents = [r for r in settings.get("recent_files", []) if r != path_str]
        recents.insert(0, path_str)
        settings.set("recent_files", recents[:20])
        self._rebuild_recent_menu()

    def _clear_recent(self):
        settings.set("recent_files", [])
        self._rebuild_recent_menu()

    # ── Theme ─────────────────────────────────────────────────────────────────
    def _apply_theme(self, theme: str):
        from PySide6.QtWidgets import QApplication
        from god_factory_editor.config import STYLES_DIR
        settings.set("theme", theme)
        qss_name = "light.qss" if theme == "light" else "dark.qss"
        qss_path = STYLES_DIR / qss_name
        if qss_path.exists():
            QApplication.instance().setStyleSheet(
                qss_path.read_text(encoding="utf-8")
            )
        else:
            # light.qss doesn't exist yet — generate minimal light theme inline
            if theme == "light":
                QApplication.instance().setStyleSheet("""
                    QMainWindow, QWidget { background-color: #f5f5f0; color: #1a1a1a; }
                    QMenuBar { background-color: #e8e8e0; color: #1a1a1a; }
                    QMenu { background-color: #f0f0e8; color: #1a1a1a; border: 1px solid #c0c0b0; }
                    QMenu::item:selected { background-color: #c8d4a0; }
                    QToolBar { background-color: #e8e8e0; border-bottom: 1px solid #c0c0b0; }
                    QDockWidget { background-color: #f0f0e8; color: #1a1a1a; }
                    QGroupBox { color: #4a7020; border: 1px solid #8fae3b; border-radius: 4px; }
                    QLabel { color: #1a1a1a; }
                    QPushButton { background-color: #e0e8d0; color: #2a4010; border: 1px solid #8fae3b;
                                  border-radius: 3px; padding: 4px 8px; }
                    QPushButton:hover { background-color: #c8d4a0; }
                    QTableWidget { background-color: #fafaf5; color: #1a1a1a;
                                   gridline-color: #d0d0c0; }
                    QHeaderView::section { background-color: #e0e0d0; color: #1a1a1a; }
                    QScrollBar:vertical { background-color: #e0e0d0; width: 10px; }
                    QScrollBar::handle:vertical { background-color: #8fae3b; border-radius: 5px; }
                    QStatusBar { background-color: #e8e8e0; color: #1a1a1a; }
                    QSlider::groove:horizontal { background-color: #d0d0c0; height: 4px; }
                    QSlider::handle:horizontal { background-color: #8fae3b; width: 12px;
                                                 margin: -4px 0; border-radius: 6px; }
                """)
            else:
                # Fall back to loading the dark qss
                dark_path = STYLES_DIR / "dark.qss"
                if dark_path.exists():
                    QApplication.instance().setStyleSheet(
                        dark_path.read_text(encoding="utf-8")
                    )
        # Sync menu and control panel buttons
        is_light = (theme == "light")
        if hasattr(self, "_act_theme"):
            self._act_theme.setChecked(is_light)
        if hasattr(self, "_control_panel") and hasattr(self._control_panel, "_theme_btn"):
            self._control_panel._theme_btn.blockSignals(True)
            self._control_panel._theme_btn.setChecked(is_light)
            self._control_panel._theme_btn.setText(f"Theme: {'Light' if is_light else 'Dark'}")
            self._control_panel._theme_btn.blockSignals(False)
        self.statusBar().showMessage(
            f"Theme switched to {'light' if is_light else 'dark'}.", 2500
        )

    def open_project_path(self, path: Path):
        """Open a project file directly (used by main.py for CLI/file-association)."""
        if self._confirm_discard():
            self._load_project(path)

    def open_project(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", settings.get("last_open_dir", ""),
            f"God Factory Projects (*{PROJECT_EXTENSION});;All Files (*)"
        )
        if path:
            self._load_project(Path(path))

    def import_external_project(self):
        if not self._confirm_discard():
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import External Editor Project",
            settings.get("last_open_dir", ""),
            external_project_file_dialog_filter(),
        )
        if not path:
            return

        settings.set("last_open_dir", str(Path(path).parent))
        self._import_external_project_path(Path(path))

    def _import_external_project_path(self, path: Path):
        from god_factory_editor.utils.external_project_import import parse_external_project

        try:
            result = parse_external_project(path)
        except Exception as exc:
            log.exception(f"External project import failed for {path}: {exc}")
            show_error(
                self,
                "Import Failed",
                f"Could not import external project:\n{exc}",
            )
            return

        if not result.segments and result.warnings:
            show_info(
                self,
                "Import Guidance",
                "\n".join(result.warnings),
            )
            return
        if not result.segments:
            show_warning(self, "Nothing Imported", "No clip segments were found in that project file.")
            return

        # Pick the first available media source path from project refs.
        chosen_video = None
        for p in result.source_candidates:
            # Try direct path first.
            if p.exists() and is_video_file(p):
                chosen_video = p
                break
            # Try relative to imported project folder.
            rel = (path.parent / p).resolve()
            if rel.exists() and is_video_file(rel):
                chosen_video = rel
                break

        if chosen_video is None:
            pick, _ = QFileDialog.getOpenFileName(
                self,
                "Select Source Video For Imported Timeline",
                str(path.parent),
                video_file_dialog_filter(),
            )
            if not pick:
                show_info(
                    self,
                    "Import Cancelled",
                    "A source video is required to map imported timeline segments."
                )
                return
            chosen_video = Path(pick)

        self._load_video(chosen_video)

        imported_clips: list[Clip] = []
        for i, seg in enumerate(result.segments, start=1):
            if seg.end <= seg.start:
                continue
            imported_clips.append(
                Clip(
                    start_time=max(0.0, seg.start),
                    end_time=max(0.0, seg.end),
                    name=(seg.name or f"Imported {i:02d}"),
                )
            )

        if not imported_clips:
            show_warning(self, "Nothing Imported", "No valid segment timings were produced from that file.")
            return

        self._clip_manager.load_clips(imported_clips)
        self._mark_unsaved()

        warn_txt = ""
        if result.warnings:
            warn_txt = "\n\nNotes:\n- " + "\n- ".join(result.warnings)

        show_info(
            self,
            "External Project Imported",
            f"Imported {len(imported_clips)} clip(s) from {result.format_name}.\n"
            f"Loaded source video: {chosen_video.name}.{warn_txt}\n\n"
            "You can now export these clips to MP4 or any supported export preset."
        )

    def save_project(self) -> bool:
        if self._project_path:
            return self._save_to(self._project_path)
        else:
            return self.save_project_as()

    def save_project_as(self) -> bool:
        last_dir = settings.get("last_open_dir", "")
        if last_dir and not Path(last_dir).exists():
            last_dir = str(Path.home())
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", last_dir,
            f"God Factory Projects (*{PROJECT_EXTENSION})"
        )
        if path:
            if not path.endswith(PROJECT_EXTENSION):
                path += PROJECT_EXTENSION
            self._project_path = Path(path)
            return self._save_to(self._project_path)
        return False

    def _save_to(self, path: Path) -> bool:
        if not self._project:
            log.warning("Save requested but there is no active project.")
            return False
        self._project.clips = self._clip_manager.clips
        try:
            saved = self._project.save(path)
            if not saved:
                raise RuntimeError("Project writer returned False (write failed).")
            self._unsaved = False
            self._update_title()
            self.statusBar().showMessage(f"Project saved: {path.name}", 3000)
            log.info(f"Project saved: {path}")
            return True
        except Exception as exc:
            log.exception(f"Save failed for {path}: {exc}")
            show_error(self, "Save Failed", str(exc))
            return False

    def _import_subtitles(self):
        """Open subtitle import dialog and apply subtitles to clips."""
        from gui.dialogs.subtitle_import_dialog import SubtitleImportDialog
        from utils.subtitle_parser import merge_captions
        
        if not self._project or not self._project.video:
            show_warning(self, "No Video Loaded",
                        "Please load a video before importing subtitles.")
            return
        
        dialog = SubtitleImportDialog(self, available_clips=self._clip_manager.clips)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        settings_dict = dialog.get_import_settings()
        captions = settings_dict["captions"]
        target = settings_dict["target"]
        offset = settings_dict["offset"]
        clip_id = settings_dict["clip_id"]
        
        if not captions:
            show_warning(self, "No Captions", "No captions were loaded.")
            return
        
        # Apply captions to selected clips
        modified_clips = 0
        
        if target == "all":
            # Apply to all clips
            for clip in self._clip_manager.clips:
                merged = merge_captions(
                    captions,
                    start_offset=offset,
                    clip_start=clip.start_time,
                    clip_end=clip.end_time,
                )
                if merged:
                    clip.captions = merged
                    modified_clips += 1
        elif target == "specific" and clip_id:
            # Apply to specific clip
            clip = self._clip_manager.get_clip(clip_id)
            if clip:
                merged = merge_captions(
                    captions,
                    start_offset=offset,
                    clip_start=clip.start_time,
                    clip_end=clip.end_time,
                )
                if merged:
                    clip.captions = merged
                    modified_clips = 1
        
        # Update UI and mark as unsaved
        self._unsaved = True
        self._update_title()
        self._clip_list.refresh()
        
        msg = f"Applied captions to {modified_clips} clip(s)."
        if modified_clips > 0:
            self.statusBar().showMessage(msg, 3000)
            log.info(msg)
        else:
            show_info(self, "Captions Applied", msg)

    # ── Project load ──────────────────────────────────────────────────────────
    def _load_video(self, path: Path):
        path = Path(path)
        log.info(f"Loading video requested: {path}")
        if not path.exists():
            log.warning(f"Video load rejected, file does not exist: {path}")
            show_error(self, "File Not Found",
                       f"The selected file does not exist:\n{path}",
                       help_anchor="loading")
            return
        if not path.is_file():
            log.warning(f"Video load rejected, path is not a file: {path}")
            show_error(self, "Invalid File",
                       f"The selected path is not a file:\n{path}",
                       help_anchor="loading")
            return
        if not is_video_file(path):
            log.warning(f"Video load rejected by extension filter: {path}")
            show_error(self, "Unsupported File",
                       f"'{path.name}' is not a recognised video format.",
                       help_anchor="loading")
            return
        try:
            meta = self._stream_manager.load(path)
        except Exception as exc:
            log.exception(f"Cannot load video {path}: {exc}")
            show_error(self, "Cannot Load Video", str(exc), help_anchor="troubleshoot")
            return

        self._video_path = path
        self._analysis_start = 0.0
        self._analysis_end = None
        self._excluded_ranges.clear()
        self._preview_file = None
        self._set_preview_mode_ui(False)
        self._project = ProjectData()
        self._project.video = meta
        self._project_path = None
        self._clip_manager.set_video_duration(meta.duration)
        self._clip_manager.load_clips([])
        self._clip_list.set_video_summary(
            f"{path.name} | {self._fmt(meta.duration)} | {meta.resolution_str} | "
            f"{meta.fps:.2f} fps | {meta.codec or 'unknown codec'}"
        )
        self._clip_list.set_video_preview(path, min(max(meta.duration * 0.25, 1.0), 120.0))
        self._timeline.set_source_label(path.name)
        self._timeline.set_source_path(path)

        # Choose proxy or original for playback
        if settings.get("proxy_enabled", True):
            self._proxy_manager.ensure_proxy(path)
            self.statusBar().showMessage("Generating proxy… (this may take a moment)")
            self._player.load(path)  # play original until proxy is ready
        else:
            self._player.load(path)

        self._timeline.set_duration(meta.duration)
        QTimer.singleShot(0, self._timeline.fit_to_width)
        self._update_title()
        self._sb_file.setText(path.name)
        self._update_proxy_badge()
        # Sync proxy button state in the control panel
        proxy_on = settings.get("proxy_enabled", True)
        if hasattr(self, "_control_panel"):
            self._control_panel.set_proxy_state(proxy_on)
        # Add to recent files
        self._add_to_recent(path)
        # Pass source to inline effects panel
        self._clip_list.set_effects_source(path)
        log.info(f"Loaded video: {path}")

    def _load_project(self, path: Path):
        try:
            project = ProjectData.load(path)
        except Exception as exc:
            show_error(self, "Cannot Open Project", str(exc))
            return

        video_path = Path(project.video.path)
        if not video_path.exists():
            show_warning(
                self, "Video Not Found",
                f"The video file is missing:\n{video_path}\n\n"
                "You can still view your clips but playback won't work."
            )
        else:
            self._load_video(video_path)

        self._clip_manager.load_clips(project.clips)
        if project.video is not None:
            self._clip_manager.set_video_duration(project.video.duration)
            self._clip_list.set_video_summary(
                f"{video_path.name} | {self._fmt(project.video.duration)} | "
                f"{project.video.resolution_str} | {project.video.fps:.2f} fps | "
                f"{project.video.codec or 'unknown codec'}"
            )
            self._clip_list.set_video_preview(video_path, min(max(project.video.duration * 0.25, 1.0), 120.0))
            self._timeline.set_source_label(video_path.name)
            self._timeline.set_source_path(video_path)
        self._project      = project
        self._project_path = path
        self._analysis_start = 0.0
        self._analysis_end = None
        self._excluded_ranges.clear()
        self._preview_file = None
        self._unsaved      = False
        self._update_title()
        self._add_to_recent(path)
        self.statusBar().showMessage(f"Loaded project: {path.name}", 3000)

    # ── Mark In / Out ─────────────────────────────────────────────────────────
    def _mark_in(self):
        if not self._video_path:
            return
        self._mark_in_time = self._player.current_position()
        self._timeline.set_in_point(self._mark_in_time)
        self.statusBar().showMessage(
            f"In point set at {self._fmt(self._mark_in_time)}  — now press O to set the end"
        )

    def _mark_out(self):
        if not self._video_path:
            return
        mark_in = getattr(self, "_mark_in_time", None)
        if mark_in is None:
            self.statusBar().showMessage("Press I first to set the clip start point.")
            return
        out = self._player.current_position()
        if out <= mark_in:
            show_warning(self, "Invalid Range",
                         "The end point must be after the start point.")
            return
        # Auto-name so the clip is created immediately — user can rename with F2
        existing_count = len(self._clip_manager.clips) + 1
        auto_name = f"Clip {existing_count:02d}"
        clip = Clip(start_time=mark_in, end_time=out, name=auto_name)
        self._clip_manager.add_clip(clip)
        self._timeline.clear_in_out()
        self._mark_in_time = None
        self.statusBar().showMessage(
            f"'{clip.name}' created ({clip.duration_str}) — select it and press F2 to rename."
        )

    # ── Clip operations ───────────────────────────────────────────────────────
    def _split_clip(self):
        pos = self._player.current_position()
        sel = self._clip_manager.selected_clip_ids
        cid = next(iter(sel)) if sel else None

        # If nothing is selected, try the clip currently under the playhead.
        if cid is None:
            for clip in self._clip_manager.clips:
                if clip.start_time < pos < clip.end_time:
                    cid = clip.id
                    self._clip_manager.select(cid, exclusive=True)
                    break

        if cid is None:
            self.statusBar().showMessage(
                "No clip at the playhead. Create a clip with I/O first, or select one to split."
            )
            return

        left, right = self._clip_manager.split_clip(cid, pos)
        if left is None or right is None:
            self.statusBar().showMessage(
                "Move the playhead inside the selected clip, then press S to split."
            )

    def _delete_selected_clip(self):
        self._do_delete_clips(list(self._clip_manager.selected_clip_ids))

    def _do_delete_clips(self, clip_ids: list):
        """Delete a list of clip ids after confirmation."""
        if not clip_ids:
            return
        clips = [self._clip_manager.get_clip(cid) for cid in clip_ids]
        clips = [c for c in clips if c]
        if not clips:
            return
        if len(clips) == 1:
            if not ask_yes_no(self, "Delete Clip",
                              f"Delete '{clips[0].name}'?"):
                return
        else:
            if not ask_yes_no(self, "Delete Clips",
                              f"Delete {len(clips)} selected clips?"):
                return
        for clip in clips:
            self._clip_manager.remove_clip(clip.id)

    def _do_delete_clip(self, clip_id: str):
        """Delete a single clip by id (used by keyboard Delete key)."""
        self._do_delete_clips([clip_id])

    def _rename_selected_clip(self):
        sel = self._clip_manager.selected_clip_ids
        if not sel:
            return
        self._do_rename_clip(next(iter(sel)))

    def _do_rename_clip(self, clip_id: str):
        """Rename a clip by opening a name dialog (used by F2 shortcut)."""
        clip = self._clip_manager.get_clip(clip_id)
        if not clip:
            return
        name, ok = QInputDialog.getText(self, "Rename Clip", "New name:", text=clip.name)
        if ok and name.strip():
            self._clip_manager.update_clip(clip_id, name=name.strip())

    def _do_rename_clip_with_name(self, clip_id: str, new_name: str):
        """Apply a new name that was already entered inline in the clip list."""
        if new_name.strip():
            self._clip_manager.update_clip(clip_id, name=new_name.strip())

    def _toggle_loop(self):
        sel = self._clip_manager.selected_clip_ids
        if not sel:
            return
        clip = self._clip_manager.get_clip(next(iter(sel)))
        if clip:
            self._player.set_loop(clip.start_time, clip.end_time)

    def _merge_clips(self):
        """Merge selected clips into one."""
        sel = list(self._clip_manager.selected_clip_ids)
        if len(sel) < 2:
            show_warning(self, "Cannot Merge",
                        "Select at least 2 clips to merge.")
            return
        
        if ask_yes_no(self, "Merge Clips",
                     f"Merge {len(sel)} selected clips into one? "
                     "Timing and effects will be preserved."):
            merged = self._clip_manager.merge_clips(sel)
            if merged:
                self.statusBar().showMessage(f"Merged {len(sel)} clips", 3000)
            else:
                show_error(self, "Merge Failed", "Could not merge selected clips.")

    def _on_clip_double_click(self, clip_id: str):
        clip = self._clip_manager.get_clip(clip_id)
        if clip:
            self._player.seek(clip.start_time)
            self._player.play()

    # ── Export ────────────────────────────────────────────────────────────────
    def _export_selected(self):
        clips = [self._clip_manager.get_clip(cid)
                 for cid in self._clip_list.checked_clip_ids()]
        clips = [c for c in clips if c]
        if not clips:
            # Fall back to selection
            clips = [self._clip_manager.get_clip(cid)
                     for cid in self._clip_manager.selected_clip_ids]
            clips = [c for c in clips if c]
        if not clips:
            show_info(self, "Nothing Selected",
                      "Tick clips in the list first, then click Export.")
            return
        self._open_export_dialog(clips)

    def _export_all(self):
        clips = self._clip_manager.clips
        if not clips:
            show_info(self, "No Clips", "Create some clips first.")
            return
        self._open_export_dialog(clips)

    def _open_export_dialog(self, clips: List[Clip]):
        source_path = self._video_path

        # Recovery path: opening a saved project can leave _video_path unset.
        if (not source_path or not source_path.exists()) and self._project and self._project.video:
            candidate = Path(self._project.video.path)
            if candidate.exists() and is_video_file(candidate):
                source_path = candidate
                self._video_path = candidate

        if not source_path or not source_path.exists():
            pick, _ = QFileDialog.getOpenFileName(
                self,
                "Locate Source Video For Export",
                settings.get("last_open_dir", ""),
                video_file_dialog_filter(),
            )
            if pick:
                source_path = Path(pick)
                self._video_path = source_path
                settings.set("last_open_dir", str(source_path.parent))

        if not source_path or not source_path.exists():
            show_error(
                self,
                "Cannot Export",
                "No valid source video is currently loaded for export.\n"
                "Load a video (or relink the project source) and try again.",
                help_anchor="export",
            )
            return

        self.statusBar().showMessage(
            f"Opening export dialog for {len(clips)} clip(s)…",
            2500,
        )
        dlg = ExportDialog(source_path, clips, self._export_engine, self)
        dlg.exec()

    # ── Auto-detect ───────────────────────────────────────────────────────────
    def _run_auto_detect(self):
        if not self._video_path:
            show_info(self, "No Video", "Load a video first.")
            return
        if self._scene_detector is not None and self._scene_detector.isRunning():
            show_info(self, "Already Running",
                      "Scene detection is already in progress.")
            return
        self._scene_detector = SceneDetector(
            video_path=self._video_path, parent=self
        )
        self._detect_scope = self._analysis_window()
        self._scene_detector.progress.connect(self._on_detect_progress)
        self._scene_detector.scenes_found.connect(self._on_scenes_found)
        self._scene_detector.failed.connect(
            lambda msg: show_error(self, "Scene Detection Failed", msg,
                                   help_anchor="autodetect")
        )
        self._scene_detector.status.connect(self._on_detect_status)
        self._detect_progress = ProgressDialog(
            title="Auto-Detecting Scenes",
            status_text="Scanning video for scene changes…",
            parent=self,
        )
        self._detect_progress.cancel_requested.connect(
            self._scene_detector.requestInterruption
        )
        self._detect_progress.show()
        self._scene_detector.start()

    def _auto_cut_boring_parts(self):
        if not self._video_path or not self._project or not self._project.video:
            show_info(self, "No Video", "Load a video first.")
            return

        from god_factory_editor.core.effects_engine import effects_engine

        cfg_dlg = AutoEditDialog(self)
        if cfg_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        cfg = cfg_dlg.values()

        analysis_start, analysis_end = self._analysis_window()
        noise_floor_db = float(settings.get("automation_noise_floor_db", -38.0))

        segments, boring = effects_engine.auto_plan_segments(
            self._video_path,
            max(0.0, analysis_end - analysis_start),
            silence_seconds=cfg["silence_seconds"],
            freeze_seconds=cfg["freeze_seconds"],
            black_seconds=cfg["black_seconds"],
            min_keep_seconds=cfg["min_keep_seconds"],
            action=cfg["action"],
            speed_factor=cfg["speed_factor"],
            noise_floor_db=noise_floor_db,
        )

        if not segments:
            show_info(self, "No Segments Generated", "Try lower thresholds in Auto-Edit settings.")
            return

        if self._clip_manager.count > 0:
            if not ask_yes_no(
                self,
                "Replace Existing Clips?",
                "Auto-edit will replace your current clip list with generated segments. Continue?"
            ):
                return

        generated = []
        for seg in segments:
            clip = Clip(
                start_time=analysis_start + seg["start"],
                end_time=analysis_start + seg["end"],
                name=seg["name"],
            )
            clip.speed = float(seg.get("speed", 1.0))
            if seg.get("kind") == "boring":
                clip.tags.append("auto-boring")
            generated.append(clip)

        generated = self._apply_excluded_ranges(generated)

        stats = effects_engine.apply_retention_rules(
            generated,
            transition_min_clip_seconds=cfg["transition_min_clip_seconds"],
            apply_sfx=cfg["apply_sfx"],
            apply_transitions=cfg["apply_transitions"],
            imply_slowmo_for_short_keep=cfg["imply_slowmo"],
        )

        if cfg["auto_captions"]:
            for clip in generated:
                clip.captions = effects_engine.generate_auto_captions_for_clip(
                    self._video_path,
                    clip,
                    min_speech_seconds=cfg["caption_min_speech_seconds"],
                )

        self._clip_manager.load_clips(generated)
        self._mark_unsaved()
        removed = sum(max(0.0, r["end"] - r["start"]) for r in boring)
        speeded = sum(max(0.0, s["end"] - s["start"]) for s in segments if s.get("speed", 1.0) > 1.01)
        caption_count = sum(len(c.captions) for c in generated)
        show_info(
            self,
            "Auto-Edit Complete",
            f"Created {len(generated)} segment{'s' if len(generated) != 1 else ''}.\n"
            f"Boring downtime detected: about {self._fmt(removed)}.\n"
            f"Fast-forward coverage: about {self._fmt(speeded)}.\n"
            f"Transitions applied: {stats['transitions']} | SFX events: {stats['sfx']} | Slow-mo hints: {stats['slowmo']}.\n"
            f"Auto-captions generated: {caption_count}.\n\n"
            "Tip: open a clip in Effects to edit speed, SFX, transitions, and captions."
        )

    def _analysis_window(self) -> tuple[float, float]:
        if not self._project or not self._project.video:
            return 0.0, 0.0
        total = float(self._project.video.duration)
        start = max(0.0, min(self._analysis_start, total))
        end = total if self._analysis_end is None else max(start, min(self._analysis_end, total))
        return start, end

    def _normalize_ranges(self, ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
        cleaned = [(max(0.0, float(a)), max(0.0, float(b))) for a, b in ranges if b > a]
        cleaned.sort(key=lambda x: x[0])
        merged: list[tuple[float, float]] = []
        for a, b in cleaned:
            if not merged or a > merged[-1][1]:
                merged.append((a, b))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        return merged

    def _apply_excluded_ranges(self, clips: list[Clip]) -> list[Clip]:
        ranges = self._normalize_ranges(self._excluded_ranges)
        if not ranges:
            return clips
        out: list[Clip] = []
        for c in clips:
            pieces = [(c.start_time, c.end_time)]
            for ra, rb in ranges:
                next_pieces: list[tuple[float, float]] = []
                for a, b in pieces:
                    if rb <= a or ra >= b:
                        next_pieces.append((a, b))
                        continue
                    if ra > a:
                        next_pieces.append((a, ra))
                    if rb < b:
                        next_pieces.append((rb, b))
                pieces = next_pieces
                if not pieces:
                    break
            for i, (a, b) in enumerate(pieces, start=1):
                if b - a < 0.8:
                    continue
                nc = c.copy()
                nc.start_time = a
                nc.end_time = b
                if len(pieces) > 1:
                    nc.name = f"{c.name} Part {i}"
                out.append(nc)
        return out

    def _set_work_start_here(self):
        if not self._project or not self._project.video:
            show_info(self, "No Video", "Load a video first.")
            return
        pos = self._player.current_position()
        self._analysis_start = max(0.0, pos)
        if self._analysis_end is not None and self._analysis_end < self._analysis_start:
            self._analysis_end = self._analysis_start
        s, e = self._analysis_window()
        self.statusBar().showMessage(
            f"Work area start set to {self._fmt(s)} (end: {self._fmt(e)})."
        )

    def _set_work_end_here(self):
        if not self._project or not self._project.video:
            show_info(self, "No Video", "Load a video first.")
            return
        pos = self._player.current_position()
        self._analysis_end = max(self._analysis_start, pos)
        s, e = self._analysis_window()
        self.statusBar().showMessage(
            f"Work area end set to {self._fmt(e)} (start: {self._fmt(s)})."
        )

    def _clear_work_area(self):
        self._analysis_start = 0.0
        self._analysis_end = None
        self._excluded_ranges.clear()
        self.statusBar().showMessage("Work area and excluded zones cleared.", 4000)

    def _exclude_selected_clips_from_automation(self):
        selected = [self._clip_manager.get_clip(cid) for cid in self._clip_manager.selected_clip_ids]
        selected = [c for c in selected if c]
        if not selected:
            show_info(self, "No Selection", "Select one or more clips to exclude from automation.")
            return
        self._excluded_ranges.extend((c.start_time, c.end_time) for c in selected)
        self._excluded_ranges = self._normalize_ranges(self._excluded_ranges)
        total = sum(max(0.0, b - a) for a, b in self._excluded_ranges)
        self.statusBar().showMessage(
            f"Excluded {len(selected)} selected clip range(s) from automation (total excluded: {self._fmt(total)}).",
            7000,
        )

    def _preview_selected_with_effects(self):
        if not self._video_path:
            show_info(self, "No Video", "Load a video first.")
            return
        sel = self._clip_manager.selected_clip_ids
        if not sel:
            show_info(self, "No Clip Selected", "Select a clip to render a preview.")
            return
        clip = self._clip_manager.get_clip(next(iter(sel)))
        if not clip:
            return

        preview_dir = TEMP_DIR / "previews"
        preview_dir.mkdir(parents=True, exist_ok=True)
        out_path = preview_dir / f"preview_{clip.id}.mp4"
        preview_len = min(20.0, max(2.0, clip.duration))

        dlg = ProgressDialog(
            title="Rendering Effect Preview",
            status_text="Building temporary preview render…",
            parent=self,
            can_cancel=False,
        )
        dlg.set_progress(10, 100)
        dlg.show()

        ok = ffmpeg.export_clip_with_effects(
            source=self._video_path,
            start=clip.start_time,
            duration=preview_len,
            output=out_path,
            speed=clip.speed,
            voice_boost_db=clip.audio_voice_boost,
            game_duck_db=clip.audio_game_duck,
            normalize=clip.audio_normalize,
            denoise=clip.audio_denoise,
            picture_brightness=clip.picture_brightness,
            picture_contrast=clip.picture_contrast,
            picture_saturation=clip.picture_saturation,
            picture_gamma=clip.picture_gamma,
            picture_sharpen=clip.picture_sharpen,
            crf=16,
            resolution=None,
        )
        dlg.set_progress(100, 100)
        dlg.on_finished()

        if not ok or not out_path.exists():
            show_error(self, "Preview Render Failed", "Could not render effect preview. Check FFmpeg logs.")
            return

        self._preview_restore_pos = clip.start_time
        self._preview_file = out_path
        self._player.load(out_path)
        self._player.seek(0.0)
        self._player.play()
        self._set_preview_mode_ui(True, "Rendered clip effects preview")
        self.statusBar().showMessage(
            f"Previewing rendered effects for '{clip.name}' ({self._fmt(preview_len)}). Use Effects -> Return To Source Playback when done.",
            9000,
        )

    def _return_to_source_preview(self):
        if not self._video_path:
            return
        # Return to full-quality source to avoid the impression of quality loss
        # after rendered preview playback.
        self._player.load(self._video_path)
        self._player.seek(self._preview_restore_pos)
        self._preview_file = None
        self._set_preview_mode_ui(False)
        self.statusBar().showMessage("Returned to full-quality source playback.", 3000)

    def _preview_clip_sequence(self):
        """Export checked clips (with effects) to temp files and play the concat."""
        if not self._video_path:
            show_info(self, "No Video", "Load a video first.")
            return
        all_clips = self._clip_manager.clips
        if not all_clips:
            show_info(self, "No Clips", "Add some clips first.")
            return
        checked_ids = set(self._clip_list.checked_clip_ids())
        clips = [c for c in all_clips if c.id in checked_ids] if checked_ids else list(all_clips)
        if not clips:
            show_info(self, "No Clips Selected", "Check at least one clip to preview.")
            return

        from god_factory_editor.gui.dialogs.progress_dialog import ProgressDialog
        from PySide6.QtWidgets import QApplication
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        out_path = tmp_dir / "sequence_preview.mp4"

        progress = ProgressDialog(
            title="Building Sequence Preview",
            status_text=f"Rendering {len(clips)} clip(s) — this may take a moment…",
            parent=self,
            can_cancel=False,
        )
        progress.show()
        QApplication.processEvents()

        # Export each clip to a temp segment file
        segments = []
        for i, clip in enumerate(clips):
            seg_path = tmp_dir / f"seg_{i:04d}.mp4"
            progress.set_status(f"Rendering clip {i+1}/{len(clips)}: {clip.name or clip.id}…")
            progress.set_progress(i, len(clips))
            QApplication.processEvents()
            ok = ffmpeg.export_clip_with_effects(
                source=self._video_path,
                start=clip.start_time,
                duration=clip.duration,
                output=seg_path,
                speed=clip.speed,
                voice_boost_db=clip.audio_voice_boost,
                game_duck_db=clip.audio_game_duck,
                normalize=clip.audio_normalize,
                denoise=clip.audio_denoise,
                picture_brightness=clip.picture_brightness,
                picture_contrast=clip.picture_contrast,
                picture_saturation=clip.picture_saturation,
                picture_gamma=clip.picture_gamma,
                picture_sharpen=clip.picture_sharpen,
                crf=17,
                resolution=None,
            )
            if ok and seg_path.exists():
                segments.append({
                    "path": seg_path,
                    "transition": clip.transition_out,
                    "transition_duration": clip.transition_duration,
                })

        if not segments:
            progress.on_finished()
            show_error(self, "Preview Failed", "No segments rendered successfully.")
            return

        progress.set_status("Concatenating segments…")
        progress.set_progress(len(clips), len(clips) + 1)
        QApplication.processEvents()

        ok_concat = ffmpeg.export_clips_concat(
            segments=segments,
            output=out_path,
            crf=17,
        )

        progress.set_progress(len(clips) + 1, len(clips) + 1)
        progress.on_finished()

        if not ok_concat or not out_path.exists():
            show_error(self, "Preview Failed",
                       "Could not concatenate clips. Check FFmpeg logs.")
            return

        self._preview_restore_pos = self._player.position()
        self._preview_file = out_path
        self._player.load(out_path)
        self._player.seek(0.0)
        self._player.play()
        self.statusBar().showMessage(
            f"Sequence preview: {len(segments)} clip(s).  "
            "Effects → Return To Source Playback when done.", 9000
        )

    def _set_preview_mode_ui(self, active: bool, mode_label: str = ""):
        """Show or hide preview affordances so users can always return quickly."""
        self._preview_banner.setVisible(active)
        if active:
            detail = f" ({mode_label})" if mode_label else ""
            self._preview_banner_label.setText(
                f"Preview mode is active{detail}. Press Esc or click Return To Timeline."
            )

    def _open_automation_wizard(self):
        if not self._video_path or not self._project or not self._project.video:
            show_info(self, "No Video", "Load a video first.")
            return

        cfg = AutomationWizardDialog(self)
        if cfg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = cfg.values()
        settings.set("automation_noise_floor_db", vals.get("noise_floor_db", -38.0))
        settings.set("voice_band_low_hz", vals.get("voice_band_low_hz", 180.0))
        settings.set("voice_band_high_hz", vals.get("voice_band_high_hz", 3400.0))
        settings.set("voice_sensitivity", vals.get("voice_sensitivity", 1.0))

        if vals["profile_id"] != "audio_cleanup" and self._clip_manager.count > 0 and vals["replace_existing"]:
            if not ask_yes_no(
                self,
                "Replace Existing Clips?",
                "This automation run will replace your current clip list. Continue?",
            ):
                return

        from god_factory_editor.core.automation_engine import automation_engine

        progress = ProgressDialog(
            title="Automation Wizard",
            status_text="Running selected pipeline…",
            parent=self,
            can_cancel=False,
        )
        progress.set_progress(10, 100)
        progress.show()

        result = automation_engine.run(
            profile_id=vals["profile_id"],
            source=self._video_path,
            total_duration=float(self._project.video.duration),
            existing_clips=self._clip_manager.clips,
            silence_seconds=vals["silence_seconds"],
            freeze_seconds=vals["freeze_seconds"],
            black_seconds=vals["black_seconds"],
            min_keep_seconds=vals["min_keep_seconds"],
            max_clips=vals["max_clips"],
            short_target_seconds=vals["short_target_seconds"],
            short_max_seconds=vals["short_max_seconds"],
            generate_captions=vals["generate_captions"],
            apply_transitions=vals["apply_transitions"],
            apply_sfx=vals["apply_sfx"],
            audio_preset_id=vals["audio_preset_id"],
            decibel_gate_lufs=vals["decibel_gate_lufs"],
            analysis_start=self._analysis_window()[0],
            analysis_end=self._analysis_window()[1],
            exclude_ranges=self._excluded_ranges,
            noise_floor_db=vals.get("noise_floor_db", -38.0),
        )
        progress.set_progress(100, 100)
        progress.on_finished()

        if result.warnings and not result.clips and vals["profile_id"] != "audio_cleanup":
            show_warning(self, "Automation Produced No Clips", "\n".join(result.warnings))
            return

        if vals["profile_id"] == "audio_cleanup":
            for c in result.clips:
                self._clip_manager.update_clip(c.id)
        else:
            if vals["replace_existing"]:
                self._clip_manager.load_clips(result.clips)
            else:
                for c in result.clips:
                    self._clip_manager.add_clip(c)

        self._mark_unsaved()
        self._clip_list.refresh()

        lines = list(result.summary_lines)
        if result.warnings:
            lines.append("")
            lines.append("Notes:")
            lines.extend(f"- {w}" for w in result.warnings)

        show_info(
            self,
            "Automation Complete",
            "\n".join(lines) if lines else "Pipeline completed.",
        )

    def _run_decibel_scan(self):
        if not self._video_path or not self._project or not self._project.video:
            show_info(self, "No Video", "Load a video first.")
            return

        from god_factory_editor.core.automation_engine import automation_engine

        total = float(self._project.video.duration)
        analysis_start, analysis_end = self._analysis_window()
        progress = ProgressDialog(
            title="Decibel / Loudness Scan",
            status_text="Scanning loudness windows across the video…",
            parent=self,
            can_cancel=False,
        )
        progress.set_progress(15, 100)
        progress.show()

        windows = automation_engine.scan_loudness_windows(
            source=self._video_path,
            total_duration=total,
            window_seconds=120.0,
            start_offset=analysis_start,
            end_offset=analysis_end,
        )

        progress.set_progress(100, 100)
        progress.on_finished()

        quiet = [w for w in windows if (w.get("integrated_lufs") is not None and w["integrated_lufs"] < -30.0)]
        hot = [w for w in windows if (w.get("integrated_lufs") is not None and w["integrated_lufs"] > -12.0)]

        def _fmtw(w: dict) -> str:
            lufs = w.get("integrated_lufs")
            lv = "n/a" if lufs is None else f"{lufs:.1f}"
            return f"{self._fmt(w['start'])}-{self._fmt(w['end'])}: {lv} LUFS"

        sample_quiet = "\n".join(_fmtw(w) for w in quiet[:6]) or "None"
        sample_hot = "\n".join(_fmtw(w) for w in hot[:6]) or "None"

        show_info(
            self,
            "Decibel Scan Complete",
            f"Scanned {len(windows)} window(s) at 120s each.\n"
            f"Quiet windows (< -30 LUFS): {len(quiet)}\n"
            f"Hot windows (> -12 LUFS): {len(hot)}\n\n"
            f"Quiet samples:\n{sample_quiet}\n\n"
            f"Hot samples:\n{sample_hot}\n\n"
            "Use Automation Wizard to gate highlights by loudness and batch-apply audio cleanup.",
        )

    def _on_detect_progress(self, pct: int):
        if hasattr(self, "_detect_progress"):
            self._detect_progress.set_progress(pct, 100)

    def _on_detect_status(self, text: str):
        self.statusBar().showMessage(text)
        if hasattr(self, "_detect_progress"):
            self._detect_progress.set_status(text)

    def _on_scenes_found(self, scenes: list):
        if hasattr(self, "_detect_progress"):
            self._detect_progress.on_finished()
        if not scenes:
            show_info(self, "No Scenes Found",
                      "No scene changes were detected. Try lowering the threshold "
                      "in Settings, or mark clips manually.")
            return
        scope = getattr(self, "_detect_scope", self._analysis_window())
        s0, s1 = scope
        banned = self._normalize_ranges(self._excluded_ranges)

        def _overlaps_banned(a: float, b: float) -> bool:
            for x, y in banned:
                if not (b <= x or a >= y):
                    return True
            return False

        accepted = 0
        for i, (start, end) in enumerate(scenes):
            if end <= s0 or start >= s1:
                continue
            start = max(start, s0)
            end = min(end, s1)
            if end - start < 0.5:
                continue
            if _overlaps_banned(start, end):
                continue
            name = f"Scene {i + 1}"
            self._clip_manager.add_clip(Clip(start_time=start, end_time=end, name=name))
            accepted += 1
        show_info(self, "Detection Complete",
                  f"{accepted} scenes were added as clips.\n"
                  "Review them on the timeline and trim as needed.")

    # ── Proxy ─────────────────────────────────────────────────────────────────
    def _toggle_proxy(self, enabled: bool):
        """Enable or disable proxy mode. Always called with an explicit bool."""
        settings.set("proxy_enabled", enabled)
        self._act_proxy.setChecked(enabled)
        # Keep control-panel button in sync
        if hasattr(self, "_control_panel"):
            self._control_panel.set_proxy_state(enabled)
        self._update_proxy_badge()
        if enabled and self._video_path:
            self._proxy_manager.ensure_proxy(self._video_path)
        elif not enabled and self._video_path:
            self._player.load(self._video_path)
        self.statusBar().showMessage(
            f"Proxy mode {'enabled — smooth 480p playback' if enabled else 'disabled — using original video'}.",
            3000,
        )

    def _on_proxy_ready(self, proxy_path: Path):
        if settings.get("proxy_enabled", True):
            self._player.load(proxy_path)
        self._update_proxy_badge()
        self.statusBar().showMessage("Proxy ready — smooth playback enabled.", 3000)

    def _on_proxy_failed(self, message: str):
        self._update_proxy_badge()
        log.warning(f"Proxy failed: {message}")
        self.statusBar().showMessage("Proxy failed. Using original video for playback.", 5000)

    def _update_proxy_badge(self):
        if not self._video_path:
            self._sb_proxy.setText("")
            return
        using = (settings.get("proxy_enabled", True)
                 and self._proxy_manager.get_proxy_path(self._video_path) is not None)
        self._sb_proxy.setText("Proxy" if using else "Original")

    # ── Settings ──────────────────────────────────────────────────────────────
    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.exec()

    def _on_settings_changed(self):
        interval_ms = settings.get("auto_save_interval", 30) * 1000
        self._autosave_timer.setInterval(interval_ms)
        self._update_proxy_badge()

    def _run_startup_maintenance(self):
        """Best-effort startup maintenance: FFmpeg readiness + repo update status."""
        self._maybe_bootstrap_ffmpeg()
        self._maybe_auto_update_from_repo()

    def _maybe_bootstrap_ffmpeg(self):
        try:
            from god_factory_editor.core.ffmpeg_manager import FFmpegManager
            ok, msg = FFmpegManager().ensure_on_launch()
            if ok:
                log.info(msg)
            else:
                log.warning(msg)
                self.statusBar().showMessage(msg, 9000)
        except Exception as exc:
            log.warning(f"FFmpeg startup check skipped: {exc}")

    def _maybe_auto_update_from_repo(self):
        try:
            from god_factory_editor.core.update_manager import UpdateManager
            updater = UpdateManager()
            if settings.get("repo_auto_update_on_launch", False):
                ok, msg = updater.pull_latest()
                self.statusBar().showMessage(msg, 8000)
                if ok:
                    show_info(self, "Update Downloaded", msg)
                return

            if settings.get("repo_auto_check_on_launch", True):
                ok, msg = updater.remote_status()
                if ok and "Update available" in msg:
                    self.statusBar().showMessage(msg + " Open Settings to pull now.", 10000)
                elif not ok:
                    log.warning(msg)
        except Exception as exc:
            log.warning(f"Auto-update skipped: {exc}")

    # ── Help ──────────────────────────────────────────────────────────────────
    def _show_help(self, topic: str = "welcome"):
        hw = HelpWindow.get_instance(self)
        hw.show_topic(topic)
        hw.show()
        hw.raise_()
        hw.activateWindow()

    # ── Player callbacks ──────────────────────────────────────────────────────
    def _on_media_loaded(self):
        dur = self._player.duration
        self._timeline.set_duration(dur)
        log.debug(f"Media loaded callback: duration={dur:.3f}s")

    def _on_player_position(self, pos: float):
        dur = self._player.duration
        self._sb_time.setText(f"{self._fmt(pos)} / {self._fmt(dur)}")

    def _on_media_error(self, msg: str):
        # If proxy playback fails, silently recover to original source.
        if self._video_path:
            proxy = self._proxy_manager.get_proxy_path(self._video_path)
            if proxy and self._player.source_path and self._player.source_path == proxy:
                log.warning("Proxy playback error; falling back to original media.")
                self._player.load(self._video_path)
                self.statusBar().showMessage(
                    "Proxy file could not be opened. Switched to original video.",
                    6000,
                )
                return

        show_error(self, "Playback Error", msg, help_anchor="troubleshoot")

    # ── Clip manager callbacks ────────────────────────────────────────────────
    def _on_clips_changed(self):
        n = len(self._clip_manager.clips)
        self._sb_clips.setText(f"{n} clip{'s' if n != 1 else ''}")

    # ── Status bar helpers ────────────────────────────────────────────────────
    def _update_sys_status(self):
        try:
            import psutil
            mem = psutil.virtual_memory()
            self._sb_mem.setText(f"RAM: {mem.percent:.0f}%")
        except Exception:
            pass

    def _rotate_tip(self):
        if not self._tip_pool:
            self._sb_tip.setText("Tip: Press F1 for in-app guides and shortcuts.")
            self._tip_timer.start(9000)
            return

        tip = self._tip_rng.choice(self._tip_pool)
        if len(self._tip_pool) > 1:
            attempts = 0
            while tip == self._tip_last and attempts < 6:
                tip = self._tip_rng.choice(self._tip_pool)
                attempts += 1
        self._tip_last = tip
        self._sb_tip.setText(f"Tip: {tip}")

        words = max(1, len(tip.split()))
        self._tip_timer.start(int(words * 1200))

    # ── Auto-save ─────────────────────────────────────────────────────────────
    def _autosave(self):
        if not self._project or not self._unsaved:
            return
        from god_factory_editor.config import APPDATA_DIR
        autosave_dir = APPDATA_DIR / "autosave"
        autosave_dir.mkdir(parents=True, exist_ok=True)
        self._autosave_path = autosave_dir / "autosave.gfve"
        try:
            self._project.clips = self._clip_manager.clips
            self._project.save(self._autosave_path)
            log.debug("Auto-saved.")
        except Exception as exc:
            log.warning(f"Auto-save failed: {exc}")

    def _check_recovery(self):
        from god_factory_editor.config import APPDATA_DIR
        candidate = APPDATA_DIR / "autosave" / "autosave.gfve"
        if candidate.exists():
            if ask_yes_no(
                self, "Recover Previous Session",
                "An auto-saved session was found.\nWould you like to recover it?"
            ):
                self._load_project(candidate)

    # ── Drag & drop ───────────────────────────────────────────────────────────
    def dragEnterEvent(self, event: QDragEnterEvent):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() == PROJECT_EXTENSION or is_video_file(p) or is_external_project_file(p):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        handled = False
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            log.info(f"Dropped path: {path}")
            if path.suffix.lower() == PROJECT_EXTENSION:
                self._load_project(path)
                handled = True
                return
            if is_external_project_file(path):
                self._import_external_project_path(path)
                handled = True
                return
            if is_video_file(path):
                if self._confirm_discard():
                    self._load_video(path)
                handled = True
                return
        if not handled:
            show_info(self, "Unsupported Drop",
                      "Drop a video file or a .gfve project file.")

    # ── Window lifecycle ──────────────────────────────────────────────────────
    def closeEvent(self, event):
        if not self._confirm_discard():
            event.ignore()
            return
        self._save_geometry()
        event.accept()

    def _confirm_discard(self) -> bool:
        if not self._unsaved:
            return True
        answer = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Save before closing?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if answer == QMessageBox.Save:
            ok = self.save_project()
            if not ok:
                self.statusBar().showMessage("Save cancelled.", 2500)
                return False
            return True
        if answer == QMessageBox.Discard:
            return True
        return False  # Cancel

    def _mark_unsaved(self):
        self._unsaved = True
        self._update_title()

    def _update_title(self):
        name = self._project_path.stem if self._project_path else (
            self._video_path.name if self._video_path else "Untitled"
        )
        dirty = " •" if self._unsaved else ""
        self.setWindowTitle(f"{APP_NAME} — {name}{dirty}")

    # ── Geometry persistence ──────────────────────────────────────────────────
    def _save_geometry(self):
        qs = QSettings("GodFactory", "VideoEditor")
        qs.setValue("geometry", self.saveGeometry())
        qs.setValue("windowState", self.saveState())

    def _restore_geometry(self):
        qs = QSettings("GodFactory", "VideoEditor")
        if geom := qs.value("geometry"):
            self.restoreGeometry(geom)
        if state := qs.value("windowState"):
            self.restoreState(state)

    # ── Clip Effects ──────────────────────────────────────────────────────────
    def _edit_selected_clip(self):
        """Backward-compatible action name used by some control-panel routes."""
        self._open_clip_effects()

    def _open_clip_effects(self, clip_id: Optional[str] = None):
        if clip_id is None:
            sel = self._clip_manager.selected_clip_ids
            if not sel:
                show_info(self, "No Clip Selected",
                          "Select a clip first, then press E to edit its effects.")
                return
            clip_id = next(iter(sel))
        clip = self._clip_manager.get_clip(clip_id)
        if not clip:
            return
        dlg = ClipEffectsDialog(clip, source_path=self._video_path, parent=self)
        dlg.effects_applied.connect(
            lambda cid: self._clip_manager.update_clip(cid)
        )
        dlg.exec()

    def _auto_suggest_transitions(self):
        """Run intelligent transition auto-placement on all clips."""
        if not self._video_path:
            show_info(self, "No Video", "Load a video first.")
            return
        clips = self._clip_manager.clips
        if len(clips) < 2:
            show_info(self, "Need More Clips",
                      "You need at least 2 clips to auto-suggest transitions.")
            return

        from god_factory_editor.core.effects_engine import effects_engine
        from god_factory_editor.gui.dialogs.progress_dialog import ProgressDialog

        progress = ProgressDialog(
            title="Auto-Suggesting Transitions",
            status_text="Analysing audio at clip boundaries…",
            parent=self,
        )
        progress.set_progress(10, 100)
        progress.show()

        suggestions = effects_engine.auto_suggest_transitions(
            self._video_path, clips, prefer_silence_gaps=True
        )
        progress.set_progress(90, 100)
        progress.on_finished()

        applied = 0
        for s in suggestions:
            clip = self._clip_manager.get_clip(s["clip_id"])
            if clip and s["transition"] != "none":
                clip.transition_out = s["transition"]
                clip.transition_duration = s["duration"]
                self._clip_manager.update_clip(clip.id)
                applied += 1

        total = len(suggestions)
        show_info(self, "Transitions Suggested",
                  f"Analysed {total} clip boundaries.\n"
                  f"{applied} transition{'s' if applied != 1 else ''} added "
                  f"(silence-safe).\n"
                  f"{total - applied} kept as hard cuts (dialogue detected).\n\n"
                  "You can review each clip's transition in Effects → Edit Clip Effects.")

    def _auto_suggest_sfx(self):
        """Auto-suggest MrBeast-style SFX placement based on speed and cut type."""
        clips = self._clip_manager.clips
        if not clips:
            show_info(self, "No Clips", "Create some clips first.")
            return

        from god_factory_editor.core.effects_engine import effects_engine
        suggestions = effects_engine.auto_suggest_sfx(clips)

        if not suggestions:
            show_info(self, "No Suggestions",
                      "No SFX placements were suggested. "
                      "Try adding speed changes to some clips first (effects like "
                      "2× or 4× get a whoosh at entry).")
            return

        added = 0
        for s in suggestions:
            clip = self._clip_manager.get_clip(s["clip_id"])
            if clip:
                evt = {
                    "name": s["sfx_id"],
                    "offset": s["offset"],
                    "volume": s["volume"],
                }
                if evt not in clip.sfx_events:
                    clip.sfx_events.append(evt)
                    self._clip_manager.update_clip(clip.id)
                    added += 1

        show_info(self, "Sound Effects Added",
                  f"{added} sound effect event{'s' if added != 1 else ''} added.\n\n"
                  "Review them via Effects → Edit Clip Effects on each clip.")

    def _export_as_single(self):
        """Export all clips as one video with transitions between them."""
        clips = self._clip_manager.clips
        if not clips:
            show_info(self, "No Clips", "Create some clips first.")
            return
        if not self._video_path:
            return
        dlg = ExportDialog(
            self._video_path, clips, self._export_engine,
            parent=self, export_as_single=True,
        )
        dlg.exec()

    # ── Global keyboard handling ─────────────────────────────────────────────
    def keyPressEvent(self, event):
        """Handle global shortcuts that need to work regardless of which widget has focus."""
        key = event.key()
        mods = event.modifiers()
        Qt_Key = Qt

        if key == Qt.Key_Escape and self._preview_file is not None:
            self._return_to_source_preview()
            event.accept()
            return

        if key == Qt.Key_Space:
            self._player.toggle_play()
            event.accept()
            return

        # Arrow seek (also handled in VideoPlayer but forwarded here if focus is elsewhere)
        if key == Qt.Key_Left:
            step = 30.0 if (mods & Qt.ShiftModifier) else 5.0
            self._player.seek_relative(-step)
            event.accept()
            return
        if key == Qt.Key_Right:
            step = 30.0 if (mods & Qt.ShiftModifier) else 5.0
            self._player.seek_relative(step)
            event.accept()
            return

        super().keyPressEvent(event)

    # ── About ─────────────────────────────────────────────────────────────────
    def _show_about(self):
        show_info(self, f"About {APP_NAME}",
                  f"<b>{APP_NAME}</b> v{APP_VERSION}<br><br>"
                  "Built for cutting 4K gaming live streams into individual "
                  "challenge highlight videos.<br><br>"
                  "Press <b>F1</b> at any time to open Help.")

    def _open_social(self, key: str):
        """Open a social/donation link from SOCIAL_LINKS in the default browser."""
        import webbrowser
        url = SOCIAL_LINKS.get(key, "")
        if url:
            webbrowser.open(url)

    # ── First-run wizard ──────────────────────────────────────────────────────
    def _show_first_run_wizard(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
        from PySide6.QtCore import Qt

        dlg = QDialog(self)
        dlg.setWindowTitle("Welcome to The God Factory Video Editor")
        dlg.setMinimumWidth(500)
        dlg.setModal(True)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)

        title = QLabel("<h2>Welcome! Here's how to make your first clip:</h2>")
        title.setWordWrap(True)
        layout.addWidget(title)

        steps = [
            ("1. Load your stream", "Drag a video file onto the window, or use <b>File → Open Video</b>"),
            ("2. Play and find your moment", "Press <b>Space</b> to play/pause. Use <b>← →</b> to jump 5 seconds, <b>Shift+← →</b> to jump 30 seconds."),
            ("3. Mark the start", "When you reach the start of a clip you want, press <b>I</b>. A gold bar appears on the timeline."),
            ("4. Mark the end", "When you reach the end of the segment, press <b>O</b>. The clip is created instantly."),
            ("5. Rename if you want", "Select the clip and press <b>F2</b> to give it a proper name."),
            ("6. Export", "Tick the checkbox next to the clips you want, then press <b>Ctrl+E</b> (Export Selected).<br>"
                          "Choose a folder and hit <b>Start Export</b>. Fast mode is near-instant — no re-encoding."),
        ]
        for step_title, step_body in steps:
            row = QHBoxLayout()
            num_lbl = QLabel(f"<b>{step_title}</b>")
            num_lbl.setMinimumWidth(170)
            row.addWidget(num_lbl)
            body_lbl = QLabel(step_body)
            body_lbl.setWordWrap(True)
            row.addWidget(body_lbl, 1)
            layout.addLayout(row)

        note = QLabel(
            "<i>Clips are segments you <u>keep</u> and export. Deleting a clip removes the marker, "
            "not the source video. You can always undo (Ctrl+Z).</i>"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b949e;")
        layout.addWidget(note)

        btn_row = QHBoxLayout()
        help_btn = QPushButton("Open Full Help (F1)")
        help_btn.clicked.connect(lambda: (dlg.accept(), self._show_help("welcome")))
        btn_row.addWidget(help_btn)
        btn_row.addStretch()
        got_it_btn = QPushButton("Got it — let's go!")
        got_it_btn.setDefault(True)
        got_it_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(got_it_btn)
        layout.addLayout(btn_row)

        dlg.exec()
        settings.set("first_run_done", True)

    # ── Misc ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt(seconds: float) -> str:
        s = max(0.0, seconds)
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sc = int(s % 60)
        return f"{h}:{m:02d}:{sc:02d}" if h else f"{m:02d}:{sc:02d}"


def _separator() -> QLabel:
    lbl = QLabel(" | ")
    lbl.setStyleSheet(f"color: {COLOURS['border']};")
    return lbl
