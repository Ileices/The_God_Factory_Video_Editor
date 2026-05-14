"""
ClipEffectsPanel — persistent inline effects editor embedded below the clip
list.  Automatically loads a clip when selected and auto-saves every change
back through ClipManager.  Includes a "Pop Out" button that opens the full
ClipEffectsDialog for a larger editing surface.

Tabs
----
Speed · Transition · Sound FX · Audio · Picture · Captions · Magic
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QFormLayout, QDoubleSpinBox, QSpinBox, QComboBox,
    QCheckBox, QGroupBox, QSlider, QListWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QColorDialog, QSizePolicy,
    QScrollArea, QGridLayout, QToolButton, QLineEdit, QProgressBar,
    QAbstractItemView,
)

from god_factory_editor.models.clip import Clip
from god_factory_editor.core.clip_manager import ClipManager
from god_factory_editor.core.effects_engine import (
    SPEED_PRESETS, TRANSITION_PRESETS, effects_engine,
)
from god_factory_editor.core.audio_enhancer import AUDIO_PRESETS


# Caption fonts commonly available / embedded in gaming/content tools
_CAPTION_FONTS = [
    "Bebas Neue", "Impact", "Anton", "Oswald", "Montserrat",
    "Roboto", "Arial Black", "Verdana Bold", "Tahoma", "Segoe UI",
    "Courier New", "OCR A Extended", "Consolas",
]

_CAPTION_EFFECTS = [
    ("none",       "None — static text"),
    ("pop",        "Pop — quick scale-in"),
    ("typewriter", "Typewriter — character by character"),
    ("slide_up",   "Slide Up — drift up from below"),
    ("fade",       "Fade In / Out"),
    ("karaoke",    "Karaoke — progressive highlight"),
    ("bounce",     "Bounce — spring landing"),
    ("zoom_in",    "Zoom In — scales from small"),
]

_CAPTION_POSITIONS = [
    ("top-left",      "↖"), ("top-center",    "↑"), ("top-right",    "↗"),
    ("middle-left",   "←"), ("middle-center", "·"), ("middle-right", "→"),
    ("bottom-left",   "↙"), ("bottom-center", "↓"), ("bottom-right", "↘"),
]


# ── Tiny colour-swatch button ─────────────────────────────────────────────────
class _ColourButton(QPushButton):
    colour_changed = Signal(str)

    def __init__(self, initial: str = "#ffffff", parent=None):
        super().__init__(parent)
        self._colour = initial
        self.setFixedSize(28, 22)
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self):
        self.setStyleSheet(
            f"background:{self._colour}; border:1px solid #555; border-radius:3px;"
        )

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._colour), self, "Pick colour")
        if c.isValid():
            self._colour = c.name()
            self._refresh()
            self.colour_changed.emit(self._colour)

    def colour(self) -> str:
        return self._colour

    def set_colour(self, hex_str: str):
        self._colour = hex_str if hex_str.startswith("#") else "#ffffff"
        self._refresh()


# ── Caption row editor ────────────────────────────────────────────────────────
class _CaptionRowEditor(QWidget):
    """One caption entry: all style controls in a compact form."""

    changed = Signal()
    delete_requested = Signal(object)  # self

    def __init__(self, cap: dict, clip_duration: float, parent=None):
        super().__init__(parent)
        self._cap = cap
        self._dur = clip_duration
        self._build()
        self._load(cap)
        # Wire all changes to emit changed
        for w in (self._start, self._end, self._font_combo, self._size_spin,
                  self._bold_chk, self._italic_chk, self._effect_combo,
                  self._pos_combo):
            if isinstance(w, QDoubleSpinBox):
                w.valueChanged.connect(self.changed)
            elif isinstance(w, QSpinBox):
                w.valueChanged.connect(self.changed)
            elif isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self.changed)
            elif isinstance(w, QCheckBox):
                w.toggled.connect(self.changed)
        self._text_edit.textChanged.connect(self.changed)
        self._txt_colour.colour_changed.connect(lambda _: self.changed.emit())
        self._bg_colour.colour_changed.connect(lambda _: self.changed.emit())
        self._bg_opacity.valueChanged.connect(self.changed)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        self.setStyleSheet(
            "background:#1c2128; border:1px solid #30363d; border-radius:6px;"
        )

        # Row 1 — timing + delete
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self._start = QDoubleSpinBox()
        self._start.setRange(0.0, max(0.01, self._dur))
        self._start.setSingleStep(0.1)
        self._start.setDecimals(3)
        self._start.setSuffix(" s")
        self._start.setFixedWidth(80)
        row1.addWidget(QLabel("Start:"))
        row1.addWidget(self._start)

        self._end = QDoubleSpinBox()
        self._end.setRange(0.0, max(0.01, self._dur))
        self._end.setSingleStep(0.1)
        self._end.setDecimals(3)
        self._end.setSuffix(" s")
        self._end.setFixedWidth(80)
        row1.addWidget(QLabel("End:"))
        row1.addWidget(self._end)
        row1.addStretch()

        del_btn = QToolButton()
        del_btn.setText("✕")
        del_btn.setToolTip("Remove caption")
        del_btn.setStyleSheet("color:#f85149;")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        row1.addWidget(del_btn)
        outer.addLayout(row1)

        # Row 2 — text content
        self._text_edit = QLineEdit()
        self._text_edit.setPlaceholderText("Caption text…")
        outer.addWidget(self._text_edit)

        # Row 3 — font + size + bold/italic
        row3 = QHBoxLayout()
        row3.setSpacing(6)
        self._font_combo = QComboBox()
        self._font_combo.addItems(_CAPTION_FONTS)
        self._font_combo.setFixedWidth(130)
        row3.addWidget(QLabel("Font:"))
        row3.addWidget(self._font_combo)

        self._size_spin = QSpinBox()
        self._size_spin.setRange(8, 120)
        self._size_spin.setValue(36)
        self._size_spin.setSuffix("px")
        self._size_spin.setFixedWidth(64)
        row3.addWidget(self._size_spin)

        self._bold_chk = QCheckBox("B")
        self._bold_chk.setStyleSheet("font-weight:bold;")
        self._italic_chk = QCheckBox("I")
        self._italic_chk.setStyleSheet("font-style:italic;")
        row3.addWidget(self._bold_chk)
        row3.addWidget(self._italic_chk)
        row3.addStretch()
        outer.addLayout(row3)

        # Row 4 — colours + effect + position
        row4 = QHBoxLayout()
        row4.setSpacing(6)
        self._txt_colour = _ColourButton("#ffffff")
        row4.addWidget(QLabel("Text:"))
        row4.addWidget(self._txt_colour)

        self._bg_colour = _ColourButton("#000000")
        row4.addWidget(QLabel("BG:"))
        row4.addWidget(self._bg_colour)

        self._bg_opacity = QSpinBox()
        self._bg_opacity.setRange(0, 100)
        self._bg_opacity.setValue(60)
        self._bg_opacity.setSuffix("%")
        self._bg_opacity.setFixedWidth(60)
        row4.addWidget(self._bg_opacity)

        self._effect_combo = QComboBox()
        for eid, elbl in _CAPTION_EFFECTS:
            self._effect_combo.addItem(elbl, eid)
        self._effect_combo.setFixedWidth(160)
        row4.addWidget(QLabel("Anim:"))
        row4.addWidget(self._effect_combo)

        self._pos_combo = QComboBox()
        for pid, psym in _CAPTION_POSITIONS:
            self._pos_combo.addItem(psym + " " + pid.replace("-", " ").title(), pid)
        self._pos_combo.setFixedWidth(140)
        row4.addWidget(QLabel("Pos:"))
        row4.addWidget(self._pos_combo)
        row4.addStretch()
        outer.addLayout(row4)

    def _load(self, cap: dict):
        self._start.setValue(float(cap.get("start", 0.0)))
        self._end.setValue(float(cap.get("end", min(self._dur, 2.0))))
        self._text_edit.setText(str(cap.get("text", "")))

        font = cap.get("font", "Bebas Neue")
        idx = self._font_combo.findText(font)
        if idx < 0:
            self._font_combo.insertItem(0, font)
            idx = 0
        self._font_combo.setCurrentIndex(idx)

        self._size_spin.setValue(int(cap.get("font_size", 36)))
        self._bold_chk.setChecked(bool(cap.get("bold", False)))
        self._italic_chk.setChecked(bool(cap.get("italic", False)))
        self._txt_colour.set_colour(cap.get("color", "#ffffff"))
        self._bg_colour.set_colour(cap.get("bg_color", "#000000"))
        self._bg_opacity.setValue(int(cap.get("bg_opacity", 0.6) * 100))

        eff_id = cap.get("effect", "pop")
        eidx = self._effect_combo.findData(eff_id)
        if eidx >= 0:
            self._effect_combo.setCurrentIndex(eidx)

        pos_id = cap.get("position", "bottom-center")
        pidx = self._pos_combo.findData(pos_id)
        if pidx >= 0:
            self._pos_combo.setCurrentIndex(pidx)

    def to_dict(self) -> dict:
        start = self._start.value()
        end   = self._end.value()
        if end <= start:
            end = min(self._dur, start + 0.5)
        return {
            "start":      round(start, 3),
            "end":        round(end, 3),
            "text":       self._text_edit.text().strip() or "Caption",
            "font":       self._font_combo.currentText(),
            "font_size":  self._size_spin.value(),
            "bold":       self._bold_chk.isChecked(),
            "italic":     self._italic_chk.isChecked(),
            "color":      self._txt_colour.colour(),
            "bg_color":   self._bg_colour.colour(),
            "bg_opacity": round(self._bg_opacity.value() / 100.0, 2),
            "position":   self._pos_combo.currentData() or "bottom-center",
            "effect":     self._effect_combo.currentData() or "pop",
        }


# ── Main panel ────────────────────────────────────────────────────────────────
class ClipEffectsPanel(QWidget):
    """
    Signals
    -------
    split_requested()        — user clicked "Split at Playhead"
    seek_requested(float)    — user clicked prev/next clip start
    popout_requested(str)    — user wants full dialog; emits clip_id
    """

    split_requested  = Signal()
    seek_requested   = Signal(float)
    popout_requested = Signal(str)

    def __init__(self, clip_manager: ClipManager, parent=None):
        super().__init__(parent)
        self._cm = clip_manager
        self._clip: Optional[Clip] = None
        self._source: Optional[Path] = None
        self._block_save = False

        # Debounce auto-save so rapid spin-box changes don't thrash
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._do_save)

        self._build_ui()
        self._show_empty()

    # ── Scaffold ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            "QFrame{background:#1c2128; border-top:2px solid #238636; "
            "border-bottom:1px solid #30363d;}"
        )
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(8, 0, 8, 0)
        hdr_row.setSpacing(6)

        self._header_lbl = QLabel("Clip Effects Editor")
        self._header_lbl.setStyleSheet("font-weight:bold; color:#e6edf3; font-size:12px;")
        hdr_row.addWidget(self._header_lbl)
        hdr_row.addStretch()

        # Navigation
        self._prev_btn = QToolButton()
        self._prev_btn.setText("◀")
        self._prev_btn.setToolTip("Previous clip")
        self._prev_btn.clicked.connect(self._prev_clip)
        hdr_row.addWidget(self._prev_btn)

        self._next_btn = QToolButton()
        self._next_btn.setText("▶")
        self._next_btn.setToolTip("Next clip")
        self._next_btn.clicked.connect(self._next_clip)
        hdr_row.addWidget(self._next_btn)

        # Split
        self._split_btn = QPushButton("✂ Split Here")
        self._split_btn.setToolTip("Split selected clip at the current playhead position")
        self._split_btn.setStyleSheet(
            "QPushButton{background:#21262d; color:#e6edf3; border:1px solid #30363d; "
            "border-radius:4px; padding:2px 8px;}"
            "QPushButton:hover{background:#30363d;}"
        )
        self._split_btn.clicked.connect(self.split_requested)
        hdr_row.addWidget(self._split_btn)

        # Pop-out
        self._popout_btn = QPushButton("⬡ Pop Out")
        self._popout_btn.setToolTip("Open full effects dialog in a floating window")
        self._popout_btn.setStyleSheet(
            "QPushButton{background:#21262d; color:#e6edf3; border:1px solid #30363d; "
            "border-radius:4px; padding:2px 8px;}"
            "QPushButton:hover{background:#30363d;}"
        )
        self._popout_btn.clicked.connect(self._on_popout)
        hdr_row.addWidget(self._popout_btn)

        root.addWidget(hdr)

        # ── Content area ──────────────────────────────────────────────────────
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(4)

        # Empty-state label
        self._empty_lbl = QLabel("Select a clip to edit its effects")
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet("color:#8b949e; font-size:12px;")
        content_layout.addWidget(self._empty_lbl)

        # Tab widget (hidden until clip loaded)
        self._tabs = QTabWidget()
        self._tabs.setVisible(False)
        self._tabs.setTabPosition(QTabWidget.North)
        self._tabs.setStyleSheet(
            "QTabBar::tab{padding:4px 10px; font-size:11px;}"
            "QTabBar::tab:selected{color:#3fb950; border-bottom:2px solid #3fb950;}"
        )
        content_layout.addWidget(self._tabs)

        # Bottom save-status bar
        self._save_lbl = QLabel("")
        self._save_lbl.setStyleSheet("color:#3fb950; font-size:10px;")
        self._save_lbl.setAlignment(Qt.AlignRight)
        content_layout.addWidget(self._save_lbl)

        root.addWidget(self._content)

    def _build_tabs(self, clip: Clip):
        """Rebuild all tab contents for the given clip."""
        self._tabs.clear()
        self._tabs.addTab(self._build_speed_tab(clip),      "Speed")
        self._tabs.addTab(self._build_transition_tab(clip), "Transition")
        self._tabs.addTab(self._build_sfx_tab(clip),        "Sound FX")
        self._tabs.addTab(self._build_audio_tab(clip),      "Audio")
        self._tabs.addTab(self._build_picture_tab(clip),    "Picture")
        self._tabs.addTab(self._build_captions_tab(clip),   "Captions ✦")
        self._tabs.addTab(self._build_magic_tab(clip),      "Magic")

    # ── Public API ────────────────────────────────────────────────────────────
    def set_clip(self, clip: Optional[Clip], source: Optional[Path] = None):
        """Load a clip into the panel (call when selection changes)."""
        self._clip = clip
        self._source = source
        if clip is None:
            self._show_empty()
        else:
            self._show_clip(clip)

    def set_source(self, source: Optional[Path]):
        self._source = source

    def refresh_from_clip(self):
        """Reload controls from current clip object (e.g. after magic template)."""
        if self._clip:
            self._show_clip(self._clip)

    # ── Display helpers ───────────────────────────────────────────────────────
    def _show_empty(self):
        self._empty_lbl.setVisible(True)
        self._tabs.setVisible(False)
        self._header_lbl.setText("Clip Effects Editor")
        self._save_lbl.setText("")
        self._split_btn.setEnabled(False)
        self._popout_btn.setEnabled(False)
        self._prev_btn.setEnabled(False)
        self._next_btn.setEnabled(False)

    def _show_clip(self, clip: Clip):
        self._empty_lbl.setVisible(False)
        self._block_save = True
        self._build_tabs(clip)
        self._block_save = False
        self._tabs.setVisible(True)
        name = clip.name or "(unnamed)"
        dur  = f"{clip.duration:.2f}s"
        self._header_lbl.setText(f"Clip Effects Editor  ─  {name}  [{dur}]")
        self._save_lbl.setText("")
        self._split_btn.setEnabled(True)
        self._popout_btn.setEnabled(True)
        idx = self._cm.get_index(clip.id)
        total = self._cm.count
        self._prev_btn.setEnabled(idx > 0)
        self._next_btn.setEnabled(idx < total - 1)

    # ── Navigation ────────────────────────────────────────────────────────────
    def _prev_clip(self):
        if not self._clip:
            return
        idx = self._cm.get_index(self._clip.id)
        if idx > 0:
            c = self._cm.clips[idx - 1]
            self._cm.select(c.id, exclusive=True)
            self.seek_requested.emit(c.start_time)

    def _next_clip(self):
        if not self._clip:
            return
        idx = self._cm.get_index(self._clip.id)
        clips = self._cm.clips
        if idx < len(clips) - 1:
            c = clips[idx + 1]
            self._cm.select(c.id, exclusive=True)
            self.seek_requested.emit(c.start_time)

    def _on_popout(self):
        if self._clip:
            self.popout_requested.emit(self._clip.id)

    # ── Auto-save ─────────────────────────────────────────────────────────────
    def _schedule_save(self):
        if not self._block_save:
            self._save_lbl.setText("saving…")
            self._save_timer.start()

    def _do_save(self):
        if self._clip is None:
            return
        self._collect_to_clip()
        self._cm.update_clip(self._clip.id)
        self._save_lbl.setText("✓ saved")

    def _collect_to_clip(self):
        """Write all control values back to self._clip in-place."""
        c = self._clip
        if c is None:
            return

        # Speed
        if hasattr(self, "_speed_spin"):
            c.speed = self._speed_spin.value()

        # Transition
        if hasattr(self, "_trans_combo"):
            c.transition_out = self._trans_combo.currentData() or "none"
        if hasattr(self, "_trans_dur_spin"):
            c.transition_duration = self._trans_dur_spin.value()

        # Audio
        if hasattr(self, "_voice_boost_spin"):
            c.audio_voice_boost = self._voice_boost_spin.value()
        if hasattr(self, "_game_duck_spin"):
            c.audio_game_duck = self._game_duck_spin.value()
        if hasattr(self, "_normalize_chk"):
            c.audio_normalize = self._normalize_chk.isChecked()
        if hasattr(self, "_denoise_chk"):
            c.audio_denoise = self._denoise_chk.isChecked()

        # Picture
        if hasattr(self, "_brightness_spin"):
            c.picture_brightness = self._brightness_spin.value()
        if hasattr(self, "_contrast_spin"):
            c.picture_contrast = self._contrast_spin.value()
        if hasattr(self, "_saturation_spin"):
            c.picture_saturation = self._saturation_spin.value()
        if hasattr(self, "_gamma_spin"):
            c.picture_gamma = self._gamma_spin.value()
        if hasattr(self, "_sharpen_spin"):
            c.picture_sharpen = self._sharpen_spin.value()

        # Captions (gathered from row editors)
        if hasattr(self, "_caption_rows"):
            c.captions = [row.to_dict() for row in self._caption_rows]

    # ── Speed tab ─────────────────────────────────────────────────────────────
    def _build_speed_tab(self, clip: Clip) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        form = QFormLayout()
        self._speed_preset_combo = QComboBox()
        for p in SPEED_PRESETS:
            self._speed_preset_combo.addItem(p["label"], p["factor"])
        self._speed_preset_combo.addItem("Custom", None)
        form.addRow("Preset:", self._speed_preset_combo)

        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0.1, 8.0)
        self._speed_spin.setSingleStep(0.1)
        self._speed_spin.setDecimals(2)
        self._speed_spin.setSuffix("×")
        self._speed_spin.setValue(clip.speed)
        form.addRow("Multiplier:", self._speed_spin)

        self._speed_dur_lbl = QLabel()
        self._speed_dur_lbl.setStyleSheet("color:#8b949e; font-size:11px;")
        form.addRow("Effective duration:", self._speed_dur_lbl)
        v.addLayout(form)

        # Sync preset → spin
        def _preset_picked(idx):
            factor = self._speed_preset_combo.itemData(idx)
            if factor is not None:
                self._speed_spin.setValue(factor)

        self._speed_preset_combo.currentIndexChanged.connect(_preset_picked)

        def _update_dur():
            spd = self._speed_spin.value()
            orig = clip.duration
            if spd > 0:
                self._speed_dur_lbl.setText(
                    f"{orig / spd:.2f}s  (original: {orig:.2f}s)"
                )
            self._schedule_save()

        self._speed_spin.valueChanged.connect(_update_dur)
        _update_dur()

        # Sync spin → preset display
        def _spin_changed(val):
            for i in range(self._speed_preset_combo.count()):
                factor = self._speed_preset_combo.itemData(i)
                if factor is not None and abs(factor - val) < 0.01:
                    self._speed_preset_combo.blockSignals(True)
                    self._speed_preset_combo.setCurrentIndex(i)
                    self._speed_preset_combo.blockSignals(False)
                    return
            custom_idx = self._speed_preset_combo.findText("Custom")
            if custom_idx >= 0:
                self._speed_preset_combo.blockSignals(True)
                self._speed_preset_combo.setCurrentIndex(custom_idx)
                self._speed_preset_combo.blockSignals(False)

        self._speed_spin.valueChanged.connect(_spin_changed)

        # Speed slider (visual)
        slider_row = QHBoxLayout()
        slow_lbl = QLabel("0.1×")
        fast_lbl = QLabel("8×")
        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setRange(10, 800)
        self._speed_slider.setValue(int(clip.speed * 100))
        slider_row.addWidget(slow_lbl)
        slider_row.addWidget(self._speed_slider, 1)
        slider_row.addWidget(fast_lbl)
        v.addLayout(slider_row)

        def _slider_moved(val):
            self._speed_spin.setValue(val / 100.0)

        self._speed_slider.valueChanged.connect(_slider_moved)
        self._speed_spin.valueChanged.connect(
            lambda v2: self._speed_slider.setValue(int(v2 * 100))
        )

        v.addStretch()
        return w

    # ── Transition tab ────────────────────────────────────────────────────────
    def _build_transition_tab(self, clip: Clip) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        form = QFormLayout()
        self._trans_combo = QComboBox()
        for t in TRANSITION_PRESETS:
            self._trans_combo.addItem(t["label"], t["id"])
        cur = self._trans_combo.findData(clip.transition_out)
        if cur >= 0:
            self._trans_combo.setCurrentIndex(cur)
        form.addRow("Transition out:", self._trans_combo)

        self._trans_dur_spin = QDoubleSpinBox()
        self._trans_dur_spin.setRange(0.1, 3.0)
        self._trans_dur_spin.setSingleStep(0.1)
        self._trans_dur_spin.setSuffix(" s")
        self._trans_dur_spin.setValue(clip.transition_duration)
        form.addRow("Duration:", self._trans_dur_spin)

        self._trans_desc_lbl = QLabel()
        self._trans_desc_lbl.setWordWrap(True)
        self._trans_desc_lbl.setStyleSheet("color:#8b949e; font-size:11px;")
        form.addRow("", self._trans_desc_lbl)
        v.addLayout(form)

        def _update_desc():
            tid = self._trans_combo.currentData()
            t = next((x for x in TRANSITION_PRESETS if x["id"] == tid), None)
            self._trans_desc_lbl.setText(t.get("description", "") if t else "")
            self._schedule_save()

        self._trans_combo.currentIndexChanged.connect(_update_desc)
        self._trans_dur_spin.valueChanged.connect(self._schedule_save)
        _update_desc()

        v.addStretch()
        return w

    # ── Sound FX tab ─────────────────────────────────────────────────────────
    def _build_sfx_tab(self, clip: Clip) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)

        self._sfx_list = QListWidget()
        for evt in clip.sfx_events:
            sfx_id = evt.get("name", "")
            label  = next((s["label"] for s in effects_engine.sfx_list
                           if s.get("id") == sfx_id), sfx_id)
            vol    = evt.get("volume", 1.0)
            offset = evt.get("offset", 0.0)
            self._sfx_list.addItem(f"  {label}  @ {offset:.2f}s  vol={vol:.0%}")
        v.addWidget(self._sfx_list)

        add_form = QFormLayout()
        self._sfx_name_combo = QComboBox()
        for s in effects_engine.sfx_list:
            self._sfx_name_combo.addItem(s["label"], s["id"])
        add_form.addRow("Sound effect:", self._sfx_name_combo)

        row2 = QHBoxLayout()
        self._sfx_offset_spin = QDoubleSpinBox()
        self._sfx_offset_spin.setRange(0.0, max(0.01, clip.duration))
        self._sfx_offset_spin.setSingleStep(0.1)
        self._sfx_offset_spin.setSuffix(" s")
        row2.addWidget(QLabel("Offset:"))
        row2.addWidget(self._sfx_offset_spin)
        self._sfx_vol_spin = QDoubleSpinBox()
        self._sfx_vol_spin.setRange(0.05, 2.0)
        self._sfx_vol_spin.setSingleStep(0.05)
        self._sfx_vol_spin.setValue(1.0)
        row2.addWidget(QLabel("Volume:"))
        row2.addWidget(self._sfx_vol_spin)
        add_form.addRow("", row2)
        v.addLayout(add_form)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add SFX")
        add_btn.clicked.connect(lambda: self._add_sfx(clip))
        del_btn = QPushButton("Remove Selected")
        del_btn.clicked.connect(lambda: self._remove_sfx(clip))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)
        v.addStretch()
        return w

    def _add_sfx(self, clip: Clip):
        sfx_id = self._sfx_name_combo.currentData()
        label  = self._sfx_name_combo.currentText()
        offset = self._sfx_offset_spin.value()
        vol    = self._sfx_vol_spin.value()
        clip.sfx_events.append({"name": sfx_id, "offset": offset, "volume": vol})
        self._sfx_list.addItem(f"  {label}  @ {offset:.2f}s  vol={vol:.0%}")
        self._cm.update_clip(clip.id)

    def _remove_sfx(self, clip: Clip):
        row = self._sfx_list.currentRow()
        if row >= 0:
            self._sfx_list.takeItem(row)
            if row < len(clip.sfx_events):
                clip.sfx_events.pop(row)
            self._cm.update_clip(clip.id)

    # ── Audio tab ─────────────────────────────────────────────────────────────
    def _build_audio_tab(self, clip: Clip) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        form = QFormLayout()
        self._audio_preset_combo = QComboBox()
        for p in AUDIO_PRESETS:
            self._audio_preset_combo.addItem(p["label"], p["id"])
        self._audio_preset_combo.currentIndexChanged.connect(self._on_audio_preset)
        form.addRow("Preset:", self._audio_preset_combo)

        self._audio_desc_lbl = QLabel()
        self._audio_desc_lbl.setWordWrap(True)
        self._audio_desc_lbl.setStyleSheet("color:#8b949e; font-size:11px;")
        form.addRow("", self._audio_desc_lbl)
        v.addLayout(form)

        grp = QGroupBox("Fine-tune")
        fine = QFormLayout(grp)

        self._voice_boost_spin = QDoubleSpinBox()
        self._voice_boost_spin.setRange(0.0, 12.0)
        self._voice_boost_spin.setSingleStep(1.0)
        self._voice_boost_spin.setSuffix(" dB")
        self._voice_boost_spin.setValue(clip.audio_voice_boost)
        self._voice_boost_spin.valueChanged.connect(self._schedule_save)
        fine.addRow("Voice boost:", self._voice_boost_spin)

        self._game_duck_spin = QDoubleSpinBox()
        self._game_duck_spin.setRange(0.0, 12.0)
        self._game_duck_spin.setSingleStep(1.0)
        self._game_duck_spin.setSuffix(" dB")
        self._game_duck_spin.setValue(clip.audio_game_duck)
        self._game_duck_spin.valueChanged.connect(self._schedule_save)
        fine.addRow("Game bass reduction:", self._game_duck_spin)

        self._normalize_chk = QCheckBox("Normalize loudness (EBU R128 / YouTube standard)")
        self._normalize_chk.setChecked(clip.audio_normalize)
        self._normalize_chk.toggled.connect(self._schedule_save)
        fine.addRow("", self._normalize_chk)

        self._denoise_chk = QCheckBox("Noise reduction")
        self._denoise_chk.setChecked(clip.audio_denoise)
        self._denoise_chk.toggled.connect(self._schedule_save)
        fine.addRow("", self._denoise_chk)
        v.addWidget(grp)

        # Analysis button (only active when source is available)
        analyse_row = QHBoxLayout()
        self._analyse_btn = QPushButton("Analyse Audio")
        self._analyse_btn.setEnabled(self._source is not None)
        self._analyse_btn.clicked.connect(lambda: self._run_audio_analysis(clip))
        self._analyse_prog = QProgressBar()
        self._analyse_prog.setRange(0, 0)
        self._analyse_prog.setVisible(False)
        self._analyse_prog.setFixedHeight(6)
        analyse_row.addWidget(self._analyse_btn)
        v.addLayout(analyse_row)
        v.addWidget(self._analyse_prog)

        self._analysis_result = QLabel("")
        self._analysis_result.setWordWrap(True)
        self._analysis_result.setStyleSheet("color:#8b949e; font-size:11px;")
        v.addWidget(self._analysis_result)

        # Match preset from clip
        self._sync_audio_preset_from_clip(clip)
        v.addStretch()
        return w

    def _on_audio_preset(self):
        pid = self._audio_preset_combo.currentData()
        for p in AUDIO_PRESETS:
            if p["id"] == pid:
                self._block_save = True
                self._voice_boost_spin.setValue(p["voice_boost"])
                self._game_duck_spin.setValue(p["game_duck"])
                self._normalize_chk.setChecked(p["normalize"])
                self._denoise_chk.setChecked(p["denoise"])
                self._audio_desc_lbl.setText(p["description"])
                self._block_save = False
                self._schedule_save()
                return

    def _sync_audio_preset_from_clip(self, clip: Clip):
        for p in AUDIO_PRESETS:
            if (abs(p["voice_boost"] - clip.audio_voice_boost) < 0.5
                    and abs(p["game_duck"] - clip.audio_game_duck) < 0.5
                    and p["normalize"] == clip.audio_normalize
                    and p["denoise"] == clip.audio_denoise):
                idx = self._audio_preset_combo.findData(p["id"])
                if idx >= 0:
                    self._audio_preset_combo.blockSignals(True)
                    self._audio_preset_combo.setCurrentIndex(idx)
                    self._audio_preset_combo.blockSignals(False)
                    self._audio_desc_lbl.setText(p["description"])
                return

    def _run_audio_analysis(self, clip: Clip):
        if not self._source:
            return
        from god_factory_editor.gui.dialogs.clip_effects_dialog import _AnalysisWorker
        self._analyse_btn.setEnabled(False)
        self._analyse_prog.setVisible(True)
        self._analysis_result.setText("Analysing…")
        self._analysis_worker = _AnalysisWorker(self._source, clip)
        self._analysis_worker.done.connect(self._on_analysis_done)
        self._analysis_worker.start()

    def _on_analysis_done(self, result: dict):
        self._analyse_prog.setVisible(False)
        self._analyse_btn.setEnabled(True)
        lines = result.get("recommendations", [])
        suggested = result.get("suggested_preset", "none")
        text = "\n".join(f"• {l}" for l in lines)
        if suggested != "none":
            text += f"\n\n→ Suggested: <b>{suggested}</b>"
            idx = self._audio_preset_combo.findData(suggested)
            if idx >= 0:
                self._audio_preset_combo.setCurrentIndex(idx)
        self._analysis_result.setText(text)

    # ── Picture tab ───────────────────────────────────────────────────────────
    def _build_picture_tab(self, clip: Clip) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        def _spin(lo, hi, step, decs, val) -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setDecimals(decs)
            s.setValue(val)
            s.valueChanged.connect(self._schedule_save)
            return s

        self._brightness_spin = _spin(-1.0,  1.0, 0.05, 2, clip.picture_brightness)
        self._contrast_spin   = _spin( 0.5,  2.0, 0.05, 2, clip.picture_contrast)
        self._saturation_spin = _spin( 0.0,  3.0, 0.1,  2, clip.picture_saturation)
        self._gamma_spin      = _spin( 0.1,  3.0, 0.1,  2, clip.picture_gamma)
        self._sharpen_spin    = _spin( 0.0,  2.0, 0.1,  2, clip.picture_sharpen)

        form.addRow("Brightness:", self._brightness_spin)
        form.addRow("Contrast:",   self._contrast_spin)
        form.addRow("Saturation:", self._saturation_spin)
        form.addRow("Gamma:",      self._gamma_spin)
        form.addRow("Sharpen:",    self._sharpen_spin)

        reset_btn = QPushButton("Reset to defaults")
        reset_btn.clicked.connect(lambda: self._reset_picture(clip))
        form.addRow("", reset_btn)
        return w

    def _reset_picture(self, clip: Clip):
        self._block_save = True
        self._brightness_spin.setValue(0.0)
        self._contrast_spin.setValue(1.0)
        self._saturation_spin.setValue(1.0)
        self._gamma_spin.setValue(1.0)
        self._sharpen_spin.setValue(0.0)
        self._block_save = False
        self._schedule_save()

    # ── Captions tab ──────────────────────────────────────────────────────────
    def _build_captions_tab(self, clip: Clip) -> QWidget:
        outer = QWidget()
        outer_v = QVBoxLayout(outer)
        outer_v.setContentsMargins(0, 0, 0, 0)
        outer_v.setSpacing(4)

        info = QLabel(
            "Add, style, and animate captions for this clip.  "
            "Each caption has its own font, colour, position, and animation."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#8b949e; font-size:11px; padding:2px 4px;")
        outer_v.addWidget(info)

        # Scroll area holds all caption row editors
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_inner = QWidget()
        self._captions_layout = QVBoxLayout(scroll_inner)
        self._captions_layout.setContentsMargins(4, 4, 4, 4)
        self._captions_layout.setSpacing(6)
        self._captions_layout.addStretch()
        scroll.setWidget(scroll_inner)
        outer_v.addWidget(scroll, 1)

        # Track row editors
        self._caption_rows: List[_CaptionRowEditor] = []
        for cap in clip.captions:
            self._add_caption_editor(cap, clip.duration)

        # Toolbar
        bar = QHBoxLayout()
        add_btn = QPushButton("+ Add Caption")
        add_btn.clicked.connect(lambda: self._add_caption_editor(
            {"start": 0.0, "end": min(clip.duration, 2.0),
             "text": "Edit caption", "font": "Bebas Neue",
             "font_size": 36, "effect": "pop", "position": "bottom-center",
             "color": "#ffffff", "bg_color": "#000000", "bg_opacity": 0.6},
            clip.duration
        ))
        auto_btn = QPushButton("Auto-Detect Speech")
        auto_btn.setEnabled(self._source is not None)
        auto_btn.clicked.connect(lambda: self._auto_detect_captions(clip))
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(lambda: self._clear_captions(clip))
        bar.addWidget(add_btn)
        bar.addWidget(auto_btn)
        bar.addStretch()
        bar.addWidget(clear_btn)
        outer_v.addLayout(bar)
        return outer

    def _add_caption_editor(self, cap: dict, clip_duration: float):
        row_widget = _CaptionRowEditor(cap, clip_duration)
        row_widget.changed.connect(self._schedule_save)
        row_widget.delete_requested.connect(self._remove_caption_editor)
        # Insert before the stretch item
        pos = self._captions_layout.count() - 1
        self._captions_layout.insertWidget(pos, row_widget)
        self._caption_rows.append(row_widget)

    def _remove_caption_editor(self, editor: _CaptionRowEditor):
        if editor in self._caption_rows:
            self._caption_rows.remove(editor)
            self._captions_layout.removeWidget(editor)
            editor.deleteLater()
            self._schedule_save()

    def _clear_captions(self, clip: Clip):
        for row in list(self._caption_rows):
            self._captions_layout.removeWidget(row)
            row.deleteLater()
        self._caption_rows.clear()
        self._schedule_save()

    def _auto_detect_captions(self, clip: Clip):
        if not self._source:
            return
        generated = effects_engine.generate_auto_captions_for_clip(
            self._source, clip,
            min_speech_seconds=0.6,
            font="Bebas Neue",
            effect="pop",
        )
        if not generated:
            return
        # Enrich with default style fields if missing
        for cap in generated:
            cap.setdefault("font_size", 36)
            cap.setdefault("bold", False)
            cap.setdefault("italic", False)
            cap.setdefault("color", "#ffffff")
            cap.setdefault("bg_color", "#000000")
            cap.setdefault("bg_opacity", 0.6)
            cap.setdefault("position", "bottom-center")

        # Clear existing and reload
        for row in list(self._caption_rows):
            self._captions_layout.removeWidget(row)
            row.deleteLater()
        self._caption_rows.clear()

        for cap in generated:
            self._add_caption_editor(cap, clip.duration)
        self._schedule_save()

    # ── Magic tab ─────────────────────────────────────────────────────────────
    def _build_magic_tab(self, clip: Clip) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        note = QLabel(
            "Apply a full creative preset in one click.  "
            "Templates tune speed, transition, audio, and picture together."
        )
        note.setWordWrap(True)
        v.addWidget(note)

        form = QFormLayout()
        self._magic_combo = QComboBox()
        self._magic_templates = effects_engine.magic_templates
        for t in self._magic_templates:
            self._magic_combo.addItem(t["label"], t["id"])
        form.addRow("Template:", self._magic_combo)

        self._magic_adaptive_chk = QCheckBox("Adaptive tune for this clip length")
        self._magic_adaptive_chk.setChecked(True)
        form.addRow("", self._magic_adaptive_chk)

        self._magic_desc = QLabel("")
        self._magic_desc.setWordWrap(True)
        self._magic_desc.setStyleSheet("color:#8b949e; font-size:11px;")
        form.addRow("", self._magic_desc)
        v.addLayout(form)

        rec_ids = effects_engine.recommend_magic_templates(clip)
        rec_labels = [
            next((t["label"] for t in self._magic_templates if t["id"] == rid), rid)
            for rid in rec_ids
        ]
        reco_lbl = QLabel("Recommended: " + (", ".join(rec_labels) or "none"))
        reco_lbl.setStyleSheet("color:#8b949e; font-size:11px;")
        reco_lbl.setWordWrap(True)
        v.addWidget(reco_lbl)

        self._magic_combo.currentIndexChanged.connect(self._update_magic_desc)
        self._update_magic_desc()

        apply_btn = QPushButton("Apply Template To This Clip")
        apply_btn.clicked.connect(lambda: self._apply_magic(clip))
        v.addWidget(apply_btn)

        self._magic_status = QLabel("")
        self._magic_status.setWordWrap(True)
        self._magic_status.setStyleSheet("color:#8b949e; font-size:11px;")
        v.addWidget(self._magic_status)

        # Save as custom template
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#30363d;")
        v.addWidget(sep)

        save_row = QHBoxLayout()
        save_row.addWidget(QLabel("Save clip settings as template:"))
        self._template_name_edit = QLineEdit()
        self._template_name_edit.setPlaceholderText("Template name…")
        save_row.addWidget(self._template_name_edit, 1)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(lambda: self._save_as_template(clip))
        save_row.addWidget(save_btn)
        v.addLayout(save_row)

        v.addStretch()
        return w

    def _update_magic_desc(self):
        tid = self._magic_combo.currentData()
        t = next((x for x in self._magic_templates if x["id"] == tid), None)
        self._magic_desc.setText(t.get("description", "") if t else "")

    def _apply_magic(self, clip: Clip):
        tid = self._magic_combo.currentData()
        adaptive = self._magic_adaptive_chk.isChecked()
        ok, msg = effects_engine.apply_magic_template(clip, tid, adaptive=adaptive)
        colour = "#3fb950" if ok else "#f85149"
        self._magic_status.setStyleSheet(f"color:{colour}; font-size:11px;")
        self._magic_status.setText(msg)
        if ok:
            # Refresh all other tabs to reflect the template's changes
            self._cm.update_clip(clip.id)
            # Reload panel controls from updated clip
            self._show_clip(clip)

    def _save_as_template(self, clip: Clip):
        name = self._template_name_edit.text().strip()
        if not name:
            self._magic_status.setText("Enter a template name first.")
            self._magic_status.setStyleSheet("color:#f85149; font-size:11px;")
            return
        try:
            from god_factory_editor.config import settings
            templates = settings.get("edit_templates", [])
            # Replace if name already exists
            templates = [t for t in templates if t.get("name") != name]
            templates.append({
                "name": name,
                "speed": clip.speed,
                "transition_out": clip.transition_out,
                "transition_duration": clip.transition_duration,
                "audio_voice_boost": clip.audio_voice_boost,
                "audio_game_duck": clip.audio_game_duck,
                "audio_normalize": clip.audio_normalize,
                "audio_denoise": clip.audio_denoise,
                "picture_brightness": clip.picture_brightness,
                "picture_contrast": clip.picture_contrast,
                "picture_saturation": clip.picture_saturation,
                "picture_gamma": clip.picture_gamma,
                "picture_sharpen": clip.picture_sharpen,
            })
            settings.set("edit_templates", templates)
            self._magic_status.setText(f"✓ Saved template '{name}'")
            self._magic_status.setStyleSheet("color:#3fb950; font-size:11px;")
        except Exception as exc:
            self._magic_status.setText(f"Save failed: {exc}")
            self._magic_status.setStyleSheet("color:#f85149; font-size:11px;")
