"""
ExportDialog — lets the user choose output folder, preset, resolution,
and shows live progress during the batch export.
"""

from __future__ import annotations
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar,
    QTextEdit, QFileDialog, QDialogButtonBox, QCheckBox,
)

from god_factory_editor.core.export_engine import ExportEngine
from god_factory_editor.models.clip import Clip
from god_factory_editor.config import EXPORT_PRESETS, settings
from god_factory_editor.utils.file_utils import human_bytes, free_space_bytes
from god_factory_editor.utils.logger import log


class ExportDialog(QDialog):
    """
    Show this dialog, call exec().
    If the user starts the export, the dialog manages the ExportEngine thread
    and emits export_finished when done.
    """

    export_finished = Signal(dict)   # {'success': [...], 'failed': [...]}

    def __init__(self, source_path: Path, clips: List[Clip],
                 engine: ExportEngine, parent=None,
                 export_as_single: bool = False):
        super().__init__(parent)
        title = "Export as Single Video" if export_as_single else "Export Clips"
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.setModal(True)

        self._source = source_path
        self._clips = clips
        self._engine = engine
        self._running = False
        self._export_as_single = export_as_single

        self._build_ui()
        self._connect_engine()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(12)

        # Info
        n = len(self._clips)
        total_dur = sum(c.duration for c in self._clips)
        mode_note = " (concatenated with transitions)" if self._export_as_single else ""
        info_lbl = QLabel(
            f"<b>Exporting {n} clip{'s' if n != 1 else ''}{mode_note}</b> "
            f"— total duration: {self._fmt_dur(total_dur)}"
        )
        main.addWidget(info_lbl)

        # Settings group
        grp = QGroupBox("Export Settings")
        form = QFormLayout(grp)

        # Output folder
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit(settings.get("export_output_dir", ""))
        dir_row.addWidget(self._dir_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(browse_btn)
        form.addRow("Output Folder:", dir_row)

        # Preset
        self._preset_combo = QComboBox()
        for key, preset in EXPORT_PRESETS.items():
            self._preset_combo.addItem(preset["label"], key)
        saved_preset = settings.get("export_preset", "fast")
        idx = self._preset_combo.findData(saved_preset)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        form.addRow("Quality:", self._preset_combo)

        # Preset description
        self._preset_desc = QLabel()
        self._preset_desc.setStyleSheet("color: #8b949e; font-size: 11px;")
        form.addRow("", self._preset_desc)

        # Space estimate
        self._space_lbl = QLabel()
        self._space_lbl.setStyleSheet("font-size: 11px;")
        form.addRow("Disk Space:", self._space_lbl)
        self._on_preset_changed()

        main.addWidget(grp)

        # Progress (hidden until export starts)
        self._prog_grp = QGroupBox("Progress")
        prog_layout = QVBoxLayout(self._prog_grp)
        self._progress = QProgressBar()
        self._progress.setRange(0, len(self._clips))
        prog_layout.addWidget(self._progress)
        self._status_lbl = QLabel("Ready")
        prog_layout.addWidget(self._status_lbl)
        self._log_box = QTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setMaximumHeight(120)
        prog_layout.addWidget(self._log_box)
        self._prog_grp.setVisible(False)
        main.addWidget(self._prog_grp)

        # Buttons
        self._btn_box = QDialogButtonBox()
        self._export_btn = self._btn_box.addButton(
            "Start Export", QDialogButtonBox.AcceptRole
        )
        self._cancel_btn = self._btn_box.addButton(
            "Cancel", QDialogButtonBox.RejectRole
        )
        self._export_btn.clicked.connect(self._start_export)
        self._cancel_btn.clicked.connect(self._on_cancel)
        main.addWidget(self._btn_box)

    # ── Engine signals ────────────────────────────────────────────────────────
    def _connect_engine(self):
        self._engine.progress.connect(self._on_progress)
        self._engine.clip_started.connect(self._on_clip_started)
        self._engine.clip_done.connect(self._on_clip_done)
        self._engine.clip_failed.connect(self._on_clip_failed)
        self._engine.all_done.connect(self._on_all_done)
        self._engine.status_message.connect(self._status_lbl.setText)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Choose Output Folder", self._dir_edit.text()
        )
        if d:
            self._dir_edit.setText(d)
            self._update_space_estimate()

    def _start_export(self):
        out_dir = Path(self._dir_edit.text().strip())
        if not out_dir.parent.exists() and not out_dir.exists():
            self._status_lbl.setText("⚠️ Output folder path is invalid.")
            return

        preset_key = self._preset_combo.currentData()
        settings.set("export_output_dir", str(out_dir))
        settings.set("export_preset", preset_key)

        self._engine.configure(
            source=self._source,
            clips=self._clips,
            output_dir=out_dir,
            preset_key=preset_key,
            export_as_single=self._export_as_single,
        )

        ok, err = self._engine.validate()
        if not ok:
            from god_factory_editor.gui.dialogs.error_handler import show_error
            show_error(self, "Cannot Export", err, help_anchor="export")
            return

        self._prog_grp.setVisible(True)
        self._export_btn.setEnabled(False)
        self._running = True
        self._engine.start()
        log.info("Export started.")

    def _on_cancel(self):
        if self._running:
            self._engine.cancel()
            self._status_lbl.setText("Cancelling…")
        else:
            self.reject()

    def _on_preset_changed(self):
        key = self._preset_combo.currentData()
        preset = EXPORT_PRESETS.get(key, {})
        self._preset_desc.setText(preset.get("description", ""))
        self._update_space_estimate()

    # ── Progress callbacks ────────────────────────────────────────────────────
    def _on_progress(self, current: int, total: int):
        self._progress.setValue(current)

    def _on_clip_started(self, name: str, idx: int):
        self._log(f"Exporting: {name}")

    def _on_clip_done(self, name: str, path: Path):
        self._log(f"Done: {name}")

    def _on_clip_failed(self, name: str, reason: str):
        self._log(f"Failed: {name} — {reason}")

    def _on_all_done(self, results: dict):
        self._running = False
        ok = len(results["success"])
        fail = len(results["failed"])
        self._status_lbl.setText(
            f"{ok} exported successfully" + (f"  |  {fail} failed" if fail else "")
        )
        self._export_btn.setEnabled(True)
        self._cancel_btn.setText("Close")
        self._cancel_btn.clicked.disconnect()
        self._cancel_btn.clicked.connect(self.accept)
        self.export_finished.emit(results)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _log(self, text: str):
        self._log_box.append(text)

    def _update_space_estimate(self):
        out_dir = Path(self._dir_edit.text().strip()) if self._dir_edit.text().strip() else Path.home()
        free = free_space_bytes(out_dir.parent if not out_dir.exists() else out_dir)
        self._space_lbl.setText(f"{human_bytes(free)} free on selected drive")

    @staticmethod
    def _fmt_dur(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h:
            return f"{h}h {m}m {s}s"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"
