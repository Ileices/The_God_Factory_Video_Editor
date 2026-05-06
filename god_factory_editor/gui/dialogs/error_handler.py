"""
Centralised error-handling dialogs — user-friendly messages for every error type.
All dialogs include a "More Info" button that shows technical details and
a "Help" link that opens the relevant help page.
"""

from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout,
)
from PySide6.QtGui import QPixmap, QIcon

from god_factory_editor.utils.logger import log


# ── Convenience wrappers ──────────────────────────────────────────────────────

def show_error(parent, title: str, message: str, detail: str = "",
               help_anchor: str = ""):
    """Show a styled error dialog."""
    dlg = _InfoDialog(parent, "error", title, message, detail, help_anchor)
    dlg.exec()


def show_warning(parent, title: str, message: str, detail: str = "",
                 help_anchor: str = ""):
    """Show a styled warning dialog."""
    dlg = _InfoDialog(parent, "warning", title, message, detail, help_anchor)
    dlg.exec()


def show_info(parent, title: str, message: str):
    """Show a simple info dialog."""
    dlg = _InfoDialog(parent, "info", title, message)
    dlg.exec()


def ask_yes_no(parent, title: str, question: str) -> bool:
    """Yes/No question — returns True if user clicked Yes."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(question)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.No)
    box.setIcon(QMessageBox.Question)
    return box.exec() == QMessageBox.Yes


def ask_yes_no_cancel(parent, title: str, question: str) -> Optional[bool]:
    """Returns True=Yes, False=No, None=Cancel."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(question)
    box.setStandardButtons(
        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
    )
    box.setDefaultButton(QMessageBox.Cancel)
    result = box.exec()
    if result == QMessageBox.Yes:
        return True
    if result == QMessageBox.No:
        return False
    return None


# ── Internal dialog class ─────────────────────────────────────────────────────

class _InfoDialog(QDialog):
    _ICONS = {
        "error":   "❌",
        "warning": "⚠️",
        "info":    "ℹ️",
    }

    def __init__(self, parent, level: str, title: str, message: str,
                 detail: str = "", help_anchor: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Icon + message
        top = QHBoxLayout()
        icon_lbl = QLabel(self._ICONS.get(level, ""))
        icon_lbl.setStyleSheet("font-size: 32px;")
        top.addWidget(icon_lbl, 0)
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        top.addWidget(msg_lbl, 1)
        layout.addLayout(top)

        # Technical detail (collapsible)
        self._detail_box: Optional[QTextEdit] = None
        if detail:
            self._detail_box = QTextEdit()
            self._detail_box.setReadOnly(True)
            self._detail_box.setPlainText(detail)
            self._detail_box.setMaximumHeight(120)
            self._detail_box.setVisible(False)
            layout.addWidget(self._detail_box)

        # Buttons
        btn_row = QHBoxLayout()

        if detail:
            more_btn = QPushButton("Show Details")
            more_btn.setCheckable(True)
            more_btn.toggled.connect(self._toggle_detail)
            btn_row.addWidget(more_btn)

        if help_anchor:
            help_btn = QPushButton("❓ Help")
            help_btn.clicked.connect(lambda: self._open_help(help_anchor))
            btn_row.addWidget(help_btn)

        btn_row.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def _toggle_detail(self, checked: bool):
        if self._detail_box:
            self._detail_box.setVisible(checked)
            self.adjustSize()

    def _open_help(self, anchor: str):
        # Import here to avoid circular imports
        try:
            from god_factory_editor.gui.help_window import HelpWindow
            hw = HelpWindow.get_instance(self)
            hw.show_topic(anchor)
            hw.show()
            hw.raise_()
        except Exception:
            pass
