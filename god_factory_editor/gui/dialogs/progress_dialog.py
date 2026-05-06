"""
Progress dialog — used for long operations (export, scene detection, proxy).
Shows a progress bar, ETA, cancel button, and live status text.
"""

from __future__ import annotations
import random
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QElapsedTimer
from PySide6.QtWidgets import (
    QDialog, QLabel, QProgressBar, QPushButton, QApplication,
    QVBoxLayout, QHBoxLayout,
)

from god_factory_editor.gui.help_window import get_help_tip_pool


class ProgressDialog(QDialog):
    """
    Usage
    -----
    dlg = ProgressDialog(parent, "Exporting clips", can_cancel=True)
    dlg.show()
    # connect your worker signals:
    worker.progress.connect(dlg.set_progress)
    worker.status_message.connect(dlg.set_status)
    worker.all_done.connect(dlg.on_finished)
    dlg.cancel_requested.connect(worker.cancel)
    """

    from PySide6.QtCore import Signal
    cancel_requested = Signal()

    def __init__(self,
                 *args,
                 parent=None,
                 title: str = "Working…",
                 status_text: str = "Preparing…",
                 can_cancel: bool = True,
                 total: int = 100):
        # Compatibility with older call style:
        # ProgressDialog(parent, title, can_cancel=True)
        # and newer style:
        # ProgressDialog(title, status_text, parent=self)
        if args:
            if hasattr(args[0], "metaObject"):
                parent = args[0]
                if len(args) > 1 and isinstance(args[1], str):
                    title = args[1]
                if len(args) > 2 and isinstance(args[2], str):
                    status_text = args[2]
            else:
                if isinstance(args[0], str):
                    title = args[0]
                if len(args) > 1 and isinstance(args[1], str):
                    status_text = args[1]

        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(540)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        self._total = max(1, int(total or 100))
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._target_percent = 0.0
        self._display_percent = 0.0
        self._phase = 0.0
        self._last_tip = ""
        self._rng = random.Random()
        self._tips = get_help_tip_pool() or [
            "Keep clips short and punchy for stronger retention.",
            "Use proxy mode for smooth playback while editing long recordings.",
            "Press I and O to mark clips quickly while watching.",
        ]

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 16)

        # Title
        title_lbl = QLabel(f"<b>{title}</b>")
        layout.addWidget(title_lbl)

        # Progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(20)
        self._bar.setStyleSheet(self._bar_stylesheet(0.0))
        layout.addWidget(self._bar)

        # Animated number readout
        self._pct_lbl = QLabel("0.0%")
        self._pct_lbl.setAlignment(Qt.AlignRight)
        self._pct_lbl.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #9ef89b;"
            "text-shadow: 0 0 8px #3fb950;"
        )
        layout.addWidget(self._pct_lbl)

        # Status text
        self._status_lbl = QLabel(status_text)
        self._status_lbl.setWordWrap(True)
        layout.addWidget(self._status_lbl)

        # Rotating help tip (1.2s per word)
        self._tip_lbl = QLabel("")
        self._tip_lbl.setWordWrap(True)
        self._tip_lbl.setStyleSheet(
            "color: #a7dba0; background: #142218; border: 1px solid #2f5a35;"
            "border-radius: 6px; padding: 8px;"
        )
        layout.addWidget(self._tip_lbl)

        # ETA
        self._eta_lbl = QLabel("")
        self._eta_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self._eta_lbl)

        # Cancel button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if can_cancel:
            self._cancel_btn = QPushButton("Cancel")
            self._cancel_btn.clicked.connect(self._on_cancel)
            btn_row.addWidget(self._cancel_btn)
        else:
            self._cancel_btn = None
        layout.addLayout(btn_row)

        # ETA update timer
        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(1000)
        self._eta_timer.timeout.connect(self._update_eta)
        self._eta_timer.start()

        # Fluid UI timer for animated progress and bar motion
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(33)
        self._ui_timer.timeout.connect(self._animate_ui)
        self._ui_timer.start()

        # Tip rotation timer (single-shot with dynamic duration)
        self._tip_timer = QTimer(self)
        self._tip_timer.setSingleShot(True)
        self._tip_timer.timeout.connect(self._rotate_tip)
        self._rotate_tip()

        self._current = 0
        self._cancelled = False

    # ── Slots ─────────────────────────────────────────────────────────────────
    def set_progress(self, current: int, total: int = None):
        if total is not None:
            self._total = max(1, int(total))

        # If callers pass percent only (0..100), accept it directly.
        if total is None and self._total <= 1 and 0 <= current <= 100:
            pct = float(current)
        elif total is None and 0 <= current <= 100 and self._total == 100:
            pct = float(current)
        else:
            self._current = max(0, int(current))
            pct = (self._current / max(1, self._total)) * 100.0

        self._target_percent = max(0.0, min(100.0, pct))
        # Keep event loop responsive after external signal bursts.
        QApplication.processEvents()

    def set_status(self, text: str):
        self._status_lbl.setText(text)

    def set_total(self, total: int):
        self._total = max(1, int(total))

    def on_finished(self, *args):
        self._eta_timer.stop()
        self._ui_timer.stop()
        self._tip_timer.stop()
        self._target_percent = 100.0
        self._display_percent = 100.0
        self._bar.setValue(100)
        self._pct_lbl.setText("100.0%")
        self._status_lbl.setText("Done!")
        self._eta_lbl.setText("")
        if self._cancel_btn:
            self._cancel_btn.setText("Close")
            self._cancel_btn.clicked.disconnect()
            self._cancel_btn.clicked.connect(self.accept)

    # ── Internal ──────────────────────────────────────────────────────────────
    def _on_cancel(self):
        if not self._cancelled:
            self._cancelled = True
            self._status_lbl.setText("Cancelling…")
            if self._cancel_btn:
                self._cancel_btn.setEnabled(False)
            self.cancel_requested.emit()

    def _update_eta(self):
        if self._total <= 0:
            return
        elapsed_ms = self._elapsed.elapsed()
        done = max(0.0, min(1.0, self._display_percent / 100.0))
        if done <= 0.0:
            return
        rate = done / (elapsed_ms / 1000.0)
        remaining = (1.0 - done) / rate if rate > 0 else 0
        self._eta_lbl.setText(f"Estimated time remaining: {_fmt_time(remaining)}")

    def _animate_ui(self):
        # Smoothly approach target percent.
        delta = self._target_percent - self._display_percent
        self._display_percent += delta * 0.22
        if abs(delta) < 0.05:
            self._display_percent = self._target_percent

        self._bar.setValue(int(round(self._display_percent)))
        self._pct_lbl.setText(f"{self._display_percent:05.1f}%")

        # Zombie-virus flow animation in bar chunk.
        self._phase = (self._phase + 0.03) % 1.0
        self._bar.setStyleSheet(self._bar_stylesheet(self._phase))

    def _bar_stylesheet(self, phase: float) -> str:
        a = max(0.0, min(1.0, phase))
        b = (a + 0.18) % 1.0
        c = (a + 0.36) % 1.0
        return (
            "QProgressBar {"
            " background: #0c120d;"
            " border: 1px solid #29452d;"
            " border-radius: 9px;"
            "}"
            "QProgressBar::chunk {"
            f" background: qlineargradient(x1:{a:.3f}, y1:0, x2:{c:.3f}, y2:1, "
            "stop:0 #2f8f4e, stop:0.45 #6ef36f, stop:0.75 #8dfc7b, stop:1 #2a5a2f);"
            " border-radius: 9px;"
            "}"
        )

    def _rotate_tip(self):
        if not self._tips:
            return
        tip = self._rng.choice(self._tips)
        if len(self._tips) > 1:
            attempts = 0
            while tip == self._last_tip and attempts < 5:
                tip = self._rng.choice(self._tips)
                attempts += 1
        self._last_tip = tip
        self._tip_lbl.setText(f"Virus Intel: {tip}")

        words = max(1, len(tip.split()))
        self._tip_timer.start(int(words * 1200))

    def closeEvent(self, event):
        # Block close button; user must cancel via button
        if not self._cancelled:
            event.ignore()
        else:
            event.accept()


def _fmt_time(secs: float) -> str:
    if secs < 60:
        return f"{int(secs)}s"
    m = int(secs // 60)
    s = int(secs % 60)
    return f"{m}m {s:02d}s"
