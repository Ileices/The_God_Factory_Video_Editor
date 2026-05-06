"""
ClipListWidget — shows all clips in a table with checkboxes,
status badges, durations, and inline editing.
"""

from __future__ import annotations
import hashlib
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QBrush, QFont, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMenu,
    QLineEdit, QSizePolicy,
)

from god_factory_editor.core.clip_manager import ClipManager
from god_factory_editor.models.clip import Clip
from god_factory_editor.utils.time_utils import seconds_to_str
from god_factory_editor.config import COLOURS
from god_factory_editor.utils.thumbnail_gen import ThumbnailGenerator


_STATUS_COLOURS = {
    "pending":  "#8b949e",
    "exported": "#3fb950",
    "failed":   "#f85149",
}

_DIFF_STARS = {1: "★☆☆☆☆", 2: "★★☆☆☆", 3: "★★★☆☆", 4: "★★★★☆", 5: "★★★★★"}

COL_CHECK = 0
COL_NAME  = 1
COL_START = 2
COL_DUR   = 3
COL_TAGS  = 4
COL_DIFF  = 5
COL_STAT  = 6


class ClipListWidget(QWidget):
    """
    Signals
    -------
    clip_seek_requested(start_seconds)
    selection_changed(list[str] clip_ids)
    rename_requested(clip_id, new_name)
    delete_requested(list[str] clip_ids)
    """

    clip_seek_requested = Signal(float)
    selection_changed = Signal(list)
    rename_requested = Signal(str, str)
    delete_requested = Signal(list)

    def __init__(self, clip_manager: ClipManager, parent=None):
        super().__init__(parent)
        self._cm = clip_manager
        self._updating = False
        self._video_summary: Optional[str] = None
        self._preview_key: Optional[str] = None
        self._thumb_gen = ThumbnailGenerator(self)
        self._thumb_gen.thumbnail_ready.connect(self._on_preview_ready)

        self._build_ui()
        self._cm.clips_changed.connect(self._refresh)
        self._cm.selection_changed.connect(self._sync_selection)
        self._refresh()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        hdr = QHBoxLayout()
        self._count_lbl = QLabel("No clips yet")
        self._count_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        hdr.addWidget(self._count_lbl)
        hdr.addStretch()

        # Search box
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter clips…")
        self._search.setFixedWidth(160)
        self._search.textChanged.connect(self._refresh)
        hdr.addWidget(self._search)

        layout.addLayout(hdr)

        self._video_info_card = QLabel(
            "<b>No video loaded</b><br><span style='color:#8b949e;'>"
            "Open a stream to see file details and clip suggestions here.</span>"
        )
        self._video_info_card.setWordWrap(True)
        self._video_info_card.setStyleSheet(
            "padding: 10px; background:#161b22; border:1px solid #30363d; "
            "border-radius: 8px; margin: 2px 0 4px 0;"
        )
        layout.addWidget(self._video_info_card)

        self._video_preview = QLabel("Preview unavailable")
        self._video_preview.setAlignment(Qt.AlignCenter)
        self._video_preview.setMinimumHeight(160)
        self._video_preview.setStyleSheet(
            "background:#11160f; border:1px solid #3f4f2b; border-radius:8px; color:#93a07d;"
        )
        layout.addWidget(self._video_preview)

        # Table
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["✓", "Name", "Start", "Duration", "Tags", "Diff", "Status"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().hide()
        self._table.setShowGrid(False)

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(COL_CHECK, QHeaderView.Fixed)
        self._table.setColumnWidth(COL_CHECK, 28)
        hh.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        hh.setSectionResizeMode(COL_START, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_DUR,   QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_TAGS,  QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_DIFF,  QHeaderView.Fixed)
        self._table.setColumnWidth(COL_DIFF, 72)
        hh.setSectionResizeMode(COL_STAT,  QHeaderView.ResizeToContents)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)

        # Checkbox click
        self._table.cellClicked.connect(self._on_cell_clicked)

        layout.addWidget(self._table)

        # Bottom toolbar
        bar = QHBoxLayout()
        self._sel_all_btn = QPushButton("Select All")
        self._sel_all_btn.clicked.connect(self._select_all_rows)
        bar.addWidget(self._sel_all_btn)
        self._sel_none_btn = QPushButton("Select None")
        self._sel_none_btn.clicked.connect(self._select_none)
        bar.addWidget(self._sel_none_btn)
        bar.addStretch()
        self._del_btn = QPushButton("Delete")
        self._del_btn.clicked.connect(self._delete_selected)
        self._del_btn.setToolTip("Delete selected clips (cannot be undone from here; use Ctrl+Z)")
        bar.addWidget(self._del_btn)
        layout.addLayout(bar)

    # ── Refresh table ─────────────────────────────────────────────────────────
    def _refresh(self):
        self._updating = True
        filter_text = self._search.text().lower()
        clips = [
            c for c in self._cm.clips
            if not filter_text or filter_text in c.name.lower()
               or any(filter_text in t.lower() for t in c.tags)
        ]

        if not clips:
            # Keep the table truly empty; do not create placeholder rows.
            # Placeholder rows can look like a phantom/invisible list and
            # interfere with row selection behavior.
            self._table.clearSpans()
            self._table.setRowCount(0)
            self._table.clearSelection()

            total = self._cm.count
            if total == 0:
                self._count_lbl.setText(self._empty_hint_text())
            else:
                self._count_lbl.setText("No clips match your current filter")
            self._updating = False
            return

        self._table.clearSpans()

        self._table.setRowCount(len(clips))
        for row, clip in enumerate(clips):
            # Checkbox column (use item checkstate)
            chk = QTableWidgetItem()
            chk.setCheckState(Qt.Checked)
            chk.setData(Qt.UserRole, clip.id)
            chk.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, COL_CHECK, chk)

            # Name
            name_item = QTableWidgetItem(clip.name or "(unnamed)")
            name_item.setData(Qt.UserRole, clip.id)
            self._table.setItem(row, COL_NAME, name_item)

            # Start
            self._table.setItem(row, COL_START,
                                 QTableWidgetItem(seconds_to_str(clip.start_time)))

            # Duration
            self._table.setItem(row, COL_DUR,
                                 QTableWidgetItem(clip.duration_str))

            # Tags
            self._table.setItem(row, COL_TAGS,
                                 QTableWidgetItem(", ".join(clip.tags)))

            # Difficulty
            stars_item = QTableWidgetItem(_DIFF_STARS.get(clip.difficulty, ""))
            stars_item.setForeground(QBrush(QColor(COLOURS["accent_gold"])))
            self._table.setItem(row, COL_DIFF, stars_item)

            # Status
            stat_item = QTableWidgetItem(clip.export_status.title())
            stat_item.setForeground(
                QBrush(QColor(_STATUS_COLOURS.get(clip.export_status, "#8b949e")))
            )
            self._table.setItem(row, COL_STAT, stat_item)

        total = self._cm.count
        shown = len(clips)
        if total == 0:
            self._count_lbl.setText(self._empty_hint_text())
        elif shown < total:
            self._count_lbl.setText(f"Showing {shown} of {total} clips")
        else:
            self._count_lbl.setText(f"{total} clip{'s' if total != 1 else ''}")

        self._updating = False

    def refresh(self):
        """Compatibility alias for older call sites in main window/control panel."""
        self._refresh()

    # ── Selection sync ────────────────────────────────────────────────────────
    def _sync_selection(self, ids: list):
        self._updating = True
        self._table.clearSelection()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, COL_NAME)
            if item and item.data(Qt.UserRole) in ids:
                self._table.selectRow(row)
        self._updating = False

    def _on_selection_changed(self):
        if self._updating:
            return
        ids = []
        seen = set()
        model = self._table.selectionModel()
        if model is not None:
            for idx in model.selectedRows(COL_NAME):
                item = self._table.item(idx.row(), COL_NAME)
                if not item:
                    continue
                cid = item.data(Qt.UserRole)
                if cid and cid not in seen:
                    ids.append(cid)
                    seen.add(cid)
        if ids:
            self._cm.select(ids[0], exclusive=True)
            for cid in ids[1:]:
                self._cm.select(cid, exclusive=False)
        else:
            self._cm.deselect_all()
        self.selection_changed.emit(ids)

    # ── Interaction ───────────────────────────────────────────────────────────
    def _on_cell_clicked(self, row: int, col: int):
        self._table.selectRow(row)
        name_item = self._table.item(row, COL_NAME)
        if name_item:
            cid = name_item.data(Qt.UserRole)
            if cid:
                self._cm.select(cid, exclusive=True)
        if col == COL_CHECK:
            return
        item = self._table.item(row, COL_NAME)
        if item:
            cid = item.data(Qt.UserRole)
            clip = self._cm.get_by_id(cid)
            if clip:
                self.clip_seek_requested.emit(clip.start_time)

    def _on_double_click(self, index):
        row = index.row()
        item = self._table.item(row, COL_NAME)
        if item:
            cid = item.data(Qt.UserRole)
            clip = self._cm.get_by_id(cid)
            if clip:
                self.clip_seek_requested.emit(clip.start_time)

    def _on_context_menu(self, pos: QPoint):
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        item = self._table.item(row, COL_NAME)
        if not item:
            return
        cid = item.data(Qt.UserRole)
        clip = self._cm.get_by_id(cid)
        if not clip:
            return

        menu = QMenu(self)
        menu.addAction("Go to Start").triggered.connect(
            lambda: self.clip_seek_requested.emit(clip.start_time))
        menu.addAction("Rename").triggered.connect(
            lambda: self._start_rename(cid))
        menu.addSeparator()
        menu.addAction("Split at Playhead").setEnabled(False)  # wired from main_window
        menu.addAction("Merge with Next").setEnabled(False)
        menu.addSeparator()
        menu.addAction("Delete").triggered.connect(
            lambda: self.delete_requested.emit([cid]))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _start_rename(self, clip_id: str):
        idx = self._cm.get_index(clip_id)
        if idx < 0:
            return
        # Find the row for this clip
        for row in range(self._table.rowCount()):
            it = self._table.item(row, COL_NAME)
            if it and it.data(Qt.UserRole) == clip_id:
                clip = self._cm.get_by_id(clip_id)
                self._table.setEditTriggers(QAbstractItemView.AllEditTriggers)
                it.setText(clip.name)
                self._table.editItem(it)
                self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)

                def _commit():
                    new_name = it.text().strip()
                    if new_name:
                        self._cm.update_clip(clip_id, name=new_name)
                        self.rename_requested.emit(clip_id, new_name)
                    else:
                        it.setText(clip.name)

                self._table.itemChanged.connect(_commit)
                return

    def _select_all_rows(self):
        self._updating = True
        for row in range(self._table.rowCount()):
            chk = self._table.item(row, COL_CHECK)
            if chk:
                chk.setCheckState(Qt.Checked)
        self._table.selectAll()
        self._updating = False
        self._cm.select_all()

    def _select_none(self):
        self._updating = True
        for row in range(self._table.rowCount()):
            chk = self._table.item(row, COL_CHECK)
            if chk:
                chk.setCheckState(Qt.Unchecked)
        self._table.clearSelection()
        self._updating = False
        self._cm.deselect_all()

    def _delete_selected(self):
        ids = []
        for row in self._table.selectedItems():
            if row.column() == COL_NAME:
                cid = row.data(Qt.UserRole)
                if cid:
                    ids.append(cid)
        if ids:
            self.delete_requested.emit(ids)

    def set_video_summary(self, summary: Optional[str]):
        self._video_summary = summary
        if summary:
            title, *rest = summary.split("|")
            detail = "<br>".join(s.strip() for s in rest if s.strip())
            if detail:
                detail = f"<span style='color:#8b949e;'>{detail}</span>"
            self._video_info_card.setText(f"<b>{title.strip()}</b><br>{detail}")
        else:
            self._video_info_card.setText(
                "<b>No video loaded</b><br><span style='color:#8b949e;'>"
                "Open a stream to see file details and clip suggestions here.</span>"
            )
        self._refresh()

    def set_video_preview(self, source, time_seconds: float = 0.0):
        if not source:
            self._preview_key = None
            self._video_preview.setText("Preview unavailable")
            self._video_preview.setPixmap(QPixmap())
            return
        source_str = str(source)
        digest = hashlib.md5(f"{source_str}|{time_seconds:.3f}".encode("utf-8")).hexdigest()[:12]
        self._preview_key = f"source_preview_{digest}"
        self._video_preview.setText("Loading preview frame…")
        self._video_preview.setPixmap(QPixmap())
        self._thumb_gen.request(self._preview_key, source, time_seconds, width=480, height=270)

    def select_clip(self, clip_id: str):
        self._sync_selection([clip_id] if clip_id else [])

    # ── Checked clips (for export) ────────────────────────────────────────────
    def checked_clip_ids(self) -> List[str]:
        """Return IDs of all clips whose checkbox is checked."""
        ids = []
        for row in range(self._table.rowCount()):
            chk = self._table.item(row, COL_CHECK)
            if chk and chk.checkState() == Qt.Checked:
                ids.append(chk.data(Qt.UserRole))
        return ids

    def _empty_hint_text(self) -> str:
        if self._video_summary:
            return f"{self._video_summary} — press I / O to mark a segment"
        return "No clips yet — press I / O to mark a segment"

    def _on_preview_ready(self, clip_id: str, pixmap: QPixmap):
        if not self._preview_key or clip_id != self._preview_key:
            return
        target = self._video_preview.size()
        if target.width() <= 0 or target.height() <= 0:
            target = self._video_preview.minimumSize()
        scaled = pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._video_preview.setPixmap(scaled)
        self._video_preview.setText("")
