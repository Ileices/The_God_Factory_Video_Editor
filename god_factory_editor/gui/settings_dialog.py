"""
SettingsDialog — user preferences: shortcuts, proxy, export, theme, FFmpeg path.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QGroupBox,
    QDialogButtonBox, QFileDialog, QKeySequenceEdit, QMessageBox,
)
from PySide6.QtGui import QKeySequence

from god_factory_editor.config import settings, FFMPEG_EXE


class SettingsDialog(QDialog):
    """Shows tabbed settings. Emits settings_changed when the user applies."""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings — The God Factory Video Editor")
        self.setMinimumWidth(560)
        self.setMinimumHeight(480)

        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_proxy_tab(),   "Video & Proxy")
        tabs.addTab(self._build_export_tab(),  "Export")
        tabs.addTab(self._build_keys_tab(),    "Shortcuts")
        tabs.addTab(self._build_tools_tab(),   "Tools & FFmpeg")
        layout.addWidget(tabs)

        # OK / Cancel / Apply
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        btns.accepted.connect(self._apply_and_close)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Apply).clicked.connect(self._apply)
        layout.addWidget(btns)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["dark", "light"])
        self._theme_combo.setCurrentText(settings.get("theme", "dark"))
        form.addRow("Theme:", self._theme_combo)

        self._autosave_spin = QSpinBox()
        self._autosave_spin.setRange(10, 300)
        self._autosave_spin.setSuffix(" seconds")
        self._autosave_spin.setValue(settings.get("auto_save_interval", 30))
        form.addRow("Auto-save every:", self._autosave_spin)

        self._undo_spin = QSpinBox()
        self._undo_spin.setRange(10, 200)
        self._undo_spin.setValue(settings.get("max_undo_steps", 50))
        form.addRow("Undo history (steps):", self._undo_spin)

        return w

    def _build_proxy_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self._proxy_chk = QCheckBox("Enable proxy mode (recommended for 4K videos)")
        self._proxy_chk.setChecked(settings.get("proxy_enabled", True))
        form.addRow("Proxy:", self._proxy_chk)

        hint = QLabel(
            "<small>Proxy creates a low-resolution preview copy for smooth scrubbing.<br>"
            "Exports always use the original high-quality video.</small>"
        )
        hint.setWordWrap(True)
        form.addRow("", hint)

        self._proxy_age_spin = QSpinBox()
        self._proxy_age_spin.setRange(1, 30)
        self._proxy_age_spin.setSuffix(" days")
        self._proxy_age_spin.setValue(settings.get("proxy_max_age_days", 7))
        form.addRow("Delete proxies older than:", self._proxy_age_spin)

        return w

    def _build_export_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self._export_dir_edit = QLineEdit(settings.get("export_output_dir", ""))
        row = QHBoxLayout()
        row.addWidget(self._export_dir_edit)
        browse = QPushButton("Browse…")
        browse.clicked.connect(
            lambda: self._export_dir_edit.setText(
                QFileDialog.getExistingDirectory(self, "Export Folder")
            )
        )
        row.addWidget(browse)
        form.addRow("Default export folder:", row)

        from god_factory_editor.config import EXPORT_PRESETS
        self._preset_combo = QComboBox()
        for key, p in EXPORT_PRESETS.items():
            self._preset_combo.addItem(p["label"], key)
        idx = self._preset_combo.findData(settings.get("export_preset", "fast"))
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)
        form.addRow("Default preset:", self._preset_combo)

        return w

    def _build_keys_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        shortcuts = settings.get("shortcuts", {})
        labels = {
            "play_pause":        "Play / Pause",
            "mark_in":           "Mark In (clip start)",
            "mark_out":          "Mark Out (clip end)",
            "seek_back":         "Seek Back 5s",
            "seek_forward":      "Seek Forward 5s",
            "seek_back_large":   "Seek Back 30s",
            "seek_forward_large":"Seek Forward 30s",
            "split":             "Split Clip at Playhead",
            "delete":            "Delete Selected Clip",
            "undo":              "Undo",
            "redo":              "Redo",
            "save":              "Save Project",
            "open":              "Open Video",
            "import_external_project": "Import External Project",
            "export_selected":   "Export Selected",
            "export_all":        "Export All",
            "auto_detect":       "Auto-Detect Scenes",
            "toggle_proxy":      "Toggle Proxy Mode",
            "loop_clip":         "Loop Clip",
            "rename":            "Rename Clip",
            "fit_timeline":      "Fit Timeline to Window",
            "help":              "Open Help",
        }

        self._key_edits: dict = {}
        form = QFormLayout()
        for key, label in labels.items():
            edit = QKeySequenceEdit(QKeySequence(shortcuts.get(key, "")))
            self._key_edits[key] = edit
            form.addRow(label + ":", edit)

        layout.addLayout(form)

        reset_btn = QPushButton("Reset All Shortcuts to Defaults")
        reset_btn.clicked.connect(self._reset_shortcuts)
        layout.addWidget(reset_btn)
        layout.addStretch()

        return w

    def _build_tools_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self._ffmpeg_edit = QLineEdit(str(FFMPEG_EXE))
        row = QHBoxLayout()
        row.addWidget(self._ffmpeg_edit)
        browse = QPushButton("Browse…")
        browse.clicked.connect(
            lambda: self._ffmpeg_edit.setText(
                QFileDialog.getOpenFileName(self, "Locate ffmpeg.exe",
                                            filter="Executables (*.exe)")[0]
                or self._ffmpeg_edit.text()
            )
        )
        row.addWidget(browse)
        form.addRow("FFmpeg path:", row)

        check_btn = QPushButton("Test FFmpeg")
        check_btn.clicked.connect(self._test_ffmpeg)
        self._ffmpeg_status = QLabel("")
        form.addRow(check_btn, self._ffmpeg_status)

        self._ffmpeg_auto_bootstrap_chk = QCheckBox("Auto-install/update bundled FFmpeg on launch")
        self._ffmpeg_auto_bootstrap_chk.setChecked(settings.get("ffmpeg_auto_bootstrap_on_launch", True))
        form.addRow("FFmpeg bootstrap:", self._ffmpeg_auto_bootstrap_chk)

        self._ffmpeg_url_edit = QLineEdit(settings.get("ffmpeg_download_url", ""))
        form.addRow("FFmpeg zip URL:", self._ffmpeg_url_edit)

        ffmpeg_update_btn = QPushButton("Install / Update FFmpeg Now")
        ffmpeg_update_btn.clicked.connect(self._install_or_update_ffmpeg)
        form.addRow(ffmpeg_update_btn)

        self._repo_url_edit = QLineEdit(settings.get("repo_url", ""))
        form.addRow("Git repo URL:", self._repo_url_edit)

        self._auto_update_chk = QCheckBox("Pull latest updates on launch (Git checkout only)")
        self._auto_update_chk.setChecked(settings.get("repo_auto_update_on_launch", False))
        form.addRow("Auto update:", self._auto_update_chk)

        self._clone_target_edit = QLineEdit(settings.get("repo_clone_target_dir", ""))
        clone_row = QHBoxLayout()
        clone_row.addWidget(self._clone_target_edit)
        clone_browse = QPushButton("Browse…")
        clone_browse.clicked.connect(
            lambda: self._clone_target_edit.setText(
                QFileDialog.getExistingDirectory(self, "Choose clone destination")
                or self._clone_target_edit.text()
            )
        )
        clone_row.addWidget(clone_browse)
        form.addRow("Clone destination:", clone_row)

        update_row = QHBoxLayout()
        status_btn = QPushButton("Check Update Status")
        status_btn.clicked.connect(self._check_update_status)
        update_row.addWidget(status_btn)
        clone_btn = QPushButton("Clone Latest Source")
        clone_btn.clicked.connect(self._clone_repo)
        update_row.addWidget(clone_btn)
        pull_btn = QPushButton("Pull Latest Updates Now")
        pull_btn.clicked.connect(self._pull_updates)
        update_row.addWidget(pull_btn)
        self._repo_status = QLabel("")
        self._repo_status.setWordWrap(True)
        form.addRow(update_row)
        form.addRow("Update status:", self._repo_status)

        return w

    # ── Apply ─────────────────────────────────────────────────────────────────
    def _apply(self):
        settings.set("theme",              self._theme_combo.currentText())
        settings.set("auto_save_interval", self._autosave_spin.value())
        settings.set("max_undo_steps",     self._undo_spin.value())
        settings.set("proxy_enabled",      self._proxy_chk.isChecked())
        settings.set("proxy_max_age_days", self._proxy_age_spin.value())
        settings.set("export_output_dir",  self._export_dir_edit.text())
        settings.set("export_preset",      self._preset_combo.currentData())
        settings.set("repo_url",           self._repo_url_edit.text().strip())
        settings.set("repo_auto_update_on_launch", self._auto_update_chk.isChecked())
        settings.set("repo_auto_check_on_launch", True)
        settings.set("repo_clone_target_dir", self._clone_target_edit.text().strip())
        settings.set("ffmpeg_auto_bootstrap_on_launch", self._ffmpeg_auto_bootstrap_chk.isChecked())
        settings.set("ffmpeg_download_url", self._ffmpeg_url_edit.text().strip())

        shortcuts = {k: e.keySequence().toString() for k, e in self._key_edits.items()}
        settings.set("shortcuts", shortcuts)

        self.settings_changed.emit()

    def _apply_and_close(self):
        self._apply()
        self.accept()

    def _reset_shortcuts(self):
        from god_factory_editor.config import DEFAULTS
        for key, edit in self._key_edits.items():
            default = DEFAULTS["shortcuts"].get(key, "")
            edit.setKeySequence(QKeySequence(default))

    def _test_ffmpeg(self):
        from god_factory_editor.utils.ffmpeg_wrapper import FFmpegWrapper
        from pathlib import Path
        ff = FFmpegWrapper(ffmpeg_path=Path(self._ffmpeg_edit.text()))
        if ff.is_available():
            self._ffmpeg_status.setText("FFmpeg is working.")
            self._ffmpeg_status.setStyleSheet("color: #3fb950;")
        else:
            self._ffmpeg_status.setText("Not found or not working.")
            self._ffmpeg_status.setStyleSheet("color: #f85149;")

    def _pull_updates(self):
        self._apply()
        from god_factory_editor.core.update_manager import UpdateManager
        ok, msg = UpdateManager().pull_latest()
        self._repo_status.setText(msg)
        self._repo_status.setStyleSheet("color: #3fb950;" if ok else "color: #f85149;")
        if ok:
            QMessageBox.information(self, "Update Pulled", msg)

    def _check_update_status(self):
        self._apply()
        from god_factory_editor.core.update_manager import UpdateManager
        ok, msg = UpdateManager().remote_status()
        self._repo_status.setText(msg)
        self._repo_status.setStyleSheet("color: #3fb950;" if ok else "color: #f85149;")

    def _clone_repo(self):
        self._apply()
        from pathlib import Path
        from god_factory_editor.core.update_manager import UpdateManager
        target = Path(self._clone_target_edit.text().strip() or settings.get("repo_clone_target_dir", ""))
        ok, msg = UpdateManager().clone_latest(target)
        self._repo_status.setText(msg)
        self._repo_status.setStyleSheet("color: #3fb950;" if ok else "color: #f85149;")
        if ok:
            QMessageBox.information(self, "Clone Complete", msg)

    def _install_or_update_ffmpeg(self):
        self._apply()
        from god_factory_editor.core.ffmpeg_manager import FFmpegManager
        ok, msg = FFmpegManager().install_or_update()
        self._ffmpeg_status.setText(msg)
        self._ffmpeg_status.setStyleSheet("color: #3fb950;" if ok else "color: #f85149;")
        if ok:
            QMessageBox.information(self, "FFmpeg Updated", msg)
