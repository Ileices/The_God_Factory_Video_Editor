"""
ClipEffectsDialog — per-clip editor for speed, transitions, sound effects,
and audio enhancement.  Opens from right-click or the Clip menu.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLabel, QComboBox, QDoubleSpinBox, QPushButton,
    QCheckBox, QGroupBox, QListWidget, QListWidgetItem,
    QSlider, QDialogButtonBox, QTextEdit, QProgressBar,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtGui import QFont

from god_factory_editor.models.clip import Clip
from god_factory_editor.core.effects_engine import (
    SPEED_PRESETS, TRANSITION_PRESETS, EffectsEngine, effects_engine,
)
from god_factory_editor.core.audio_enhancer import AUDIO_PRESETS, AudioEnhancer


class _AnalysisWorker(QThread):
    """Background thread for audio analysis so the UI doesn't freeze."""
    done = Signal(dict)

    def __init__(self, source: Path, clip: Clip):
        super().__init__()
        self._source = source
        self._clip = clip

    def run(self):
        enhancer = AudioEnhancer()
        result = enhancer.analyse_clip(self._source, self._clip)
        self.done.emit(result)


class ClipEffectsDialog(QDialog):
    """
    Tabbed dialog:
      1. Speed        — speed multiplier + resulting duration preview
      2. Transition   — transition type out of this clip + duration
      3. Sound Effects— add/remove SFX events with offset + volume
      4. Audio        — voice boost preset + custom sliders + auto-analysis
    """

    effects_applied = Signal(str)   # clip_id

    def __init__(self,
                 clip: Clip,
                 source_path: Optional[Path] = None,
                 parent=None):
        super().__init__(parent)
        self._clip = clip
        self._source = source_path
        self._worker: Optional[_AnalysisWorker] = None

        self.setWindowTitle(f"Effects — {clip.name or 'Clip'}")
        self.setMinimumWidth(540)
        self.setMinimumHeight(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Clip info banner
        info = QLabel(
            f"<b>{clip.name}</b>  ·  {clip.duration_str}  ·  "
            f"{clip.start_str} → {clip.end_str}"
        )
        info.setStyleSheet("padding: 6px; background:#161b22; border-radius:4px;")
        layout.addWidget(info)

        tabs = QTabWidget()
        tabs.addTab(self._build_speed_tab(),      "Speed")
        tabs.addTab(self._build_transition_tab(), "Transition")
        tabs.addTab(self._build_sfx_tab(),        "Sound FX")
        tabs.addTab(self._build_audio_tab(),      "Audio")
        tabs.addTab(self._build_picture_tab(),    "Picture")
        tabs.addTab(self._build_captions_tab(),   "Captions")
        tabs.addTab(self._build_magic_tab(),      "Magic")
        layout.addWidget(tabs)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._apply)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ── Speed tab ─────────────────────────────────────────────────────────────
    def _build_speed_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        # Preset selector
        form = QFormLayout()
        self._speed_combo = QComboBox()
        for p in SPEED_PRESETS:
            self._speed_combo.addItem(p["label"], p["value"])
        # Select current
        cur = self._clip.speed
        found = False
        for i, p in enumerate(SPEED_PRESETS):
            if abs(p["value"] - cur) < 0.001:
                self._speed_combo.setCurrentIndex(i)
                found = True
                break
        if not found:
            self._speed_combo.addItem(f"Custom: {cur}×", cur)
            self._speed_combo.setCurrentIndex(self._speed_combo.count() - 1)
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        form.addRow("Speed preset:", self._speed_combo)

        # Custom spin
        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0.1, 64.0)
        self._speed_spin.setSingleStep(0.25)
        self._speed_spin.setDecimals(2)
        self._speed_spin.setSuffix("×")
        self._speed_spin.setValue(self._clip.speed)
        self._speed_spin.valueChanged.connect(self._on_speed_spin_changed)
        form.addRow("Custom value:", self._speed_spin)
        v.addLayout(form)

        # Duration preview
        self._speed_result_lbl = QLabel()
        self._speed_result_lbl.setStyleSheet("color:#8b949e; font-size:12px;")
        v.addWidget(self._speed_result_lbl)
        self._refresh_speed_preview()

        # Help note
        note = QLabel(
            "<small><b>Tip:</b> <b>Slow-mo</b>: 0.5× or 0.25×.  "
            "<b>Hyper-lapse</b>: 8× or more to turn a 2-hour segment into "
            "a 15-minute highlight.  Speeds over 2× remove the original audio "
            "(no intelligible speech at high speed).</small>"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#8b949e;")
        v.addWidget(note)
        v.addStretch()
        return w

    def _on_speed_changed(self):
        val = self._speed_combo.currentData()
        if val is not None:
            self._speed_spin.blockSignals(True)
            self._speed_spin.setValue(val)
            self._speed_spin.blockSignals(False)
        self._refresh_speed_preview()

    def _on_speed_spin_changed(self, val: float):
        self._speed_combo.blockSignals(True)
        # Try to select matching preset
        matched = False
        for i in range(self._speed_combo.count()):
            if abs((self._speed_combo.itemData(i) or 0) - val) < 0.001:
                self._speed_combo.setCurrentIndex(i)
                matched = True
                break
        if not matched:
            # Custom — add/update custom entry
            last = self._speed_combo.count() - 1
            if "Custom" in self._speed_combo.itemText(last):
                self._speed_combo.setItemText(last, f"Custom: {val}×")
                self._speed_combo.setItemData(last, val)
                self._speed_combo.setCurrentIndex(last)
            else:
                self._speed_combo.addItem(f"Custom: {val}×", val)
                self._speed_combo.setCurrentIndex(self._speed_combo.count() - 1)
        self._speed_combo.blockSignals(False)
        self._refresh_speed_preview()

    def _refresh_speed_preview(self):
        speed = self._speed_spin.value()
        original = self._clip.duration
        new_dur = original / speed
        change = original - new_dur
        direction = "shorter" if change > 0 else "longer"
        self._speed_result_lbl.setText(
            f"Original: {self._fmt(original)}  →  "
            f"Output: {self._fmt(new_dur)} "
            f"({abs(change):.1f}s {direction})"
        )

    # ── Transition tab ────────────────────────────────────────────────────────
    def _build_transition_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self._trans_combo = QComboBox()
        for t in TRANSITION_PRESETS:
            self._trans_combo.addItem(t["label"], t["id"])
        idx = self._trans_combo.findData(self._clip.transition_out)
        if idx >= 0:
            self._trans_combo.setCurrentIndex(idx)
        self._trans_combo.currentIndexChanged.connect(self._on_trans_changed)
        form.addRow("Transition out:", self._trans_combo)

        self._trans_dur_spin = QDoubleSpinBox()
        self._trans_dur_spin.setRange(0.1, 3.0)
        self._trans_dur_spin.setSingleStep(0.1)
        self._trans_dur_spin.setSuffix(" sec")
        self._trans_dur_spin.setValue(self._clip.transition_duration)
        form.addRow("Duration:", self._trans_dur_spin)

        self._trans_desc = QLabel()
        self._trans_desc.setStyleSheet("color:#8b949e; font-size:11px;")
        self._trans_desc.setWordWrap(True)
        form.addRow("", self._trans_desc)
        self._on_trans_changed()

        note = QLabel(
            "<small><b>Tip:</b> Transitions are applied when you export multiple clips "
            "together as a single video. The transition plays between this clip "
            "and the next one in sequence.<br><br>"
            "<b>Dialogue-safe</b>: Use the Auto-Suggest button in the Effects menu "
            "to intelligently place transitions only where it is silent.</small>"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#8b949e;")
        form.addRow("", note)
        return w

    def _on_trans_changed(self):
        tid = self._trans_combo.currentData()
        descriptions = {
            "none": "Hard cut — the video jumps directly to the next clip.",
            "fade": "Smooth fade between clips.",
            "fadeblack": "Clip fades to black, then next clip fades in.",
            "dissolve": "Both clips blend together during the transition.",
            "wipeleft": "New clip wipes in from the right.",
            "wiperight": "New clip wipes in from the left.",
            "slideleft": "Next clip slides in from the right.",
            "slideright": "Next clip slides in from the left.",
            "zoom": "Zooms into the cut point.",
            "pixelize": "Pixelizes out then in (retro/fun style).",
            "circleopen": "Circle opens to reveal the next clip.",
        }
        self._trans_desc.setText(descriptions.get(tid, ""))

    # ── Sound FX tab ──────────────────────────────────────────────────────────
    def _build_sfx_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)

        lbl = QLabel(
            "<b>Sound Effects</b> — play a short sound at a specific point "
            "in the clip during export."
        )
        lbl.setWordWrap(True)
        v.addWidget(lbl)

        # Current SFX list
        self._sfx_list = QListWidget()
        for evt in self._clip.sfx_events:
            self._sfx_list.addItem(
                f"  {evt.get('name','?')}  @ {evt.get('offset',0):.2f}s  "
                f"vol={evt.get('volume',0.7):.0%}"
            )
        v.addWidget(self._sfx_list)

        # Add controls
        add_row = QHBoxLayout()
        self._sfx_name_combo = QComboBox()
        library = effects_engine.sfx_list
        for sfx in library:
            self._sfx_name_combo.addItem(sfx["label"], sfx["id"])
        add_row.addWidget(QLabel("Effect:"))
        add_row.addWidget(self._sfx_name_combo, stretch=2)

        add_row.addWidget(QLabel("At:"))
        self._sfx_offset_spin = QDoubleSpinBox()
        self._sfx_offset_spin.setRange(0.0, max(0.1, self._clip.duration))
        self._sfx_offset_spin.setSuffix("s")
        self._sfx_offset_spin.setSingleStep(0.5)
        add_row.addWidget(self._sfx_offset_spin)

        add_row.addWidget(QLabel("Vol:"))
        self._sfx_vol_spin = QDoubleSpinBox()
        self._sfx_vol_spin.setRange(0.0, 1.0)
        self._sfx_vol_spin.setSingleStep(0.1)
        self._sfx_vol_spin.setValue(0.7)
        add_row.addWidget(self._sfx_vol_spin)
        v.addLayout(add_row)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add")
        add_btn.clicked.connect(self._add_sfx)
        del_btn = QPushButton("Remove Selected")
        del_btn.clicked.connect(self._remove_sfx)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        note = QLabel(
            "<small><b>Tip:</b> MrBeast style: add a <b>Whoosh</b> at 0.0s for a speed-ramp "
            "opener, or a <b>Boom</b> at the very end to punch the cut out.\n"
            "Effects are mixed at the specified volume over the original audio.</small>"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#8b949e;")
        v.addWidget(note)
        return w

    def _add_sfx(self):
        sfx_id = self._sfx_name_combo.currentData()
        label  = self._sfx_name_combo.currentText()
        offset = self._sfx_offset_spin.value()
        vol    = self._sfx_vol_spin.value()
        evt = {"name": sfx_id, "offset": offset, "volume": vol}
        self._clip.sfx_events.append(evt)
        self._sfx_list.addItem(f"  {label}  @ {offset:.2f}s  vol={vol:.0%}")

    def _remove_sfx(self):
        row = self._sfx_list.currentRow()
        if row >= 0:
            self._sfx_list.takeItem(row)
            if row < len(self._clip.sfx_events):
                self._clip.sfx_events.pop(row)

    # ── Audio tab ─────────────────────────────────────────────────────────────
    def _build_audio_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        # Preset selector
        form = QFormLayout()
        self._audio_preset_combo = QComboBox()
        for p in AUDIO_PRESETS:
            self._audio_preset_combo.addItem(p["label"], p["id"])
        self._audio_preset_combo.currentIndexChanged.connect(self._on_audio_preset_changed)
        form.addRow("Enhancement preset:", self._audio_preset_combo)

        self._audio_desc_lbl = QLabel()
        self._audio_desc_lbl.setWordWrap(True)
        self._audio_desc_lbl.setStyleSheet("color:#8b949e; font-size:11px;")
        form.addRow("", self._audio_desc_lbl)
        v.addLayout(form)

        # Manual overrides
        grp = QGroupBox("Fine-tune")
        fine = QFormLayout(grp)

        self._voice_boost_spin = QDoubleSpinBox()
        self._voice_boost_spin.setRange(0.0, 12.0)
        self._voice_boost_spin.setSingleStep(1.0)
        self._voice_boost_spin.setSuffix(" dB")
        self._voice_boost_spin.setValue(self._clip.audio_voice_boost)
        fine.addRow("Voice boost:", self._voice_boost_spin)

        self._game_duck_spin = QDoubleSpinBox()
        self._game_duck_spin.setRange(0.0, 12.0)
        self._game_duck_spin.setSingleStep(1.0)
        self._game_duck_spin.setSuffix(" dB")
        self._game_duck_spin.setValue(self._clip.audio_game_duck)
        fine.addRow("Game bass reduction:", self._game_duck_spin)

        self._normalize_chk = QCheckBox("Normalize loudness (EBU R128 / YouTube standard)")
        self._normalize_chk.setChecked(self._clip.audio_normalize)
        fine.addRow("", self._normalize_chk)

        self._denoise_chk = QCheckBox("Noise reduction (requires recent FFmpeg)")
        self._denoise_chk.setChecked(self._clip.audio_denoise)
        fine.addRow("", self._denoise_chk)

        v.addWidget(grp)

        # Auto-analysis
        analyse_row = QHBoxLayout()
        self._analyse_btn = QPushButton("Analyse this clip's audio")
        self._analyse_btn.setEnabled(bool(self._source))
        self._analyse_btn.clicked.connect(self._run_analysis)
        self._analyse_prog = QProgressBar()
        self._analyse_prog.setRange(0, 0)   # indeterminate
        self._analyse_prog.setVisible(False)
        self._analyse_prog.setFixedHeight(6)
        analyse_row.addWidget(self._analyse_btn)
        v.addLayout(analyse_row)
        v.addWidget(self._analyse_prog)

        self._analysis_result = QLabel("")
        self._analysis_result.setWordWrap(True)
        self._analysis_result.setStyleSheet("color:#8b949e; font-size:11px;")
        v.addWidget(self._analysis_result)

        # Initialise preset label from current clip values
        self._sync_preset_from_clip()
        v.addStretch()
        return w

    def _build_picture_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self._brightness_spin = QDoubleSpinBox()
        self._brightness_spin.setRange(-1.0, 1.0)
        self._brightness_spin.setSingleStep(0.05)
        self._brightness_spin.setDecimals(2)
        self._brightness_spin.setValue(self._clip.picture_brightness)
        form.addRow("Brightness:", self._brightness_spin)

        self._contrast_spin = QDoubleSpinBox()
        self._contrast_spin.setRange(0.5, 2.0)
        self._contrast_spin.setSingleStep(0.05)
        self._contrast_spin.setDecimals(2)
        self._contrast_spin.setValue(self._clip.picture_contrast)
        form.addRow("Contrast:", self._contrast_spin)

        self._saturation_spin = QDoubleSpinBox()
        self._saturation_spin.setRange(0.0, 3.0)
        self._saturation_spin.setSingleStep(0.1)
        self._saturation_spin.setDecimals(2)
        self._saturation_spin.setValue(self._clip.picture_saturation)
        form.addRow("Saturation:", self._saturation_spin)

        self._gamma_spin = QDoubleSpinBox()
        self._gamma_spin.setRange(0.1, 3.0)
        self._gamma_spin.setSingleStep(0.1)
        self._gamma_spin.setDecimals(2)
        self._gamma_spin.setValue(self._clip.picture_gamma)
        form.addRow("Gamma:", self._gamma_spin)

        self._sharpen_spin = QDoubleSpinBox()
        self._sharpen_spin.setRange(0.0, 2.0)
        self._sharpen_spin.setSingleStep(0.1)
        self._sharpen_spin.setDecimals(2)
        self._sharpen_spin.setValue(self._clip.picture_sharpen)
        form.addRow("Sharpen:", self._sharpen_spin)

        note = QLabel(
            "<small><b>Tip:</b> Use this for dark gameplay, flat footage, washed-out colors, "
            "or a small sharpness boost before export. These are export-time filters "
            "and do not modify your source video.</small>"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#8b949e;")
        form.addRow("", note)
        return w

    def _build_captions_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)

        info = QLabel(
            "Auto-captions are editable placeholders based on detected speech regions. "
            "Edit text, timing, font name, and splash effect after detection."
        )
        info.setWordWrap(True)
        v.addWidget(info)

        self._cap_table = QTableWidget(0, 5)
        self._cap_table.setHorizontalHeaderLabels(["Start", "End", "Text", "Font", "Effect"])
        hh = self._cap_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._cap_table.verticalHeader().hide()
        v.addWidget(self._cap_table)

        row = QHBoxLayout()
        add_btn = QPushButton("+ Add Caption")
        add_btn.clicked.connect(self._add_caption_row)
        del_btn = QPushButton("Remove Selected")
        del_btn.clicked.connect(self._remove_caption_row)
        auto_btn = QPushButton("Auto-Detect Speech Regions")
        auto_btn.setEnabled(bool(self._source))
        auto_btn.clicked.connect(self._auto_detect_captions)
        row.addWidget(add_btn)
        row.addWidget(del_btn)
        row.addWidget(auto_btn)
        row.addStretch()
        v.addLayout(row)

        self._load_caption_rows()
        return w

    def _build_magic_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        note = QLabel(
            "Apply a full creative preset in one click. Templates tune speed, transition, "
            "audio enhancement, and picture look together."
        )
        note.setWordWrap(True)
        v.addWidget(note)

        form = QFormLayout()
        self._magic_combo = QComboBox()
        self._magic_templates = effects_engine.magic_templates
        for t in self._magic_templates:
            self._magic_combo.addItem(t["label"], t["id"])
        self._magic_combo.currentIndexChanged.connect(self._on_magic_template_changed)
        form.addRow("Template:", self._magic_combo)

        self._magic_adaptive_chk = QCheckBox("Adaptive tune for this clip length")
        self._magic_adaptive_chk.setChecked(True)
        form.addRow("", self._magic_adaptive_chk)

        self._magic_desc = QLabel("")
        self._magic_desc.setWordWrap(True)
        self._magic_desc.setStyleSheet("color:#8b949e; font-size:11px;")
        form.addRow("", self._magic_desc)
        v.addLayout(form)

        rec_ids = effects_engine.recommend_magic_templates(self._clip)
        rec_labels = []
        for rid in rec_ids:
            found = next((t["label"] for t in self._magic_templates if t["id"] == rid), rid)
            rec_labels.append(found)
        self._magic_reco = QLabel("Recommended: " + ", ".join(rec_labels))
        self._magic_reco.setStyleSheet("color:#8b949e; font-size:11px;")
        self._magic_reco.setWordWrap(True)
        v.addWidget(self._magic_reco)

        apply_btn = QPushButton("Apply Template To This Clip")
        apply_btn.clicked.connect(self._apply_magic_template)
        v.addWidget(apply_btn)

        self._magic_status = QLabel("")
        self._magic_status.setWordWrap(True)
        self._magic_status.setStyleSheet("color:#8b949e; font-size:11px;")
        v.addWidget(self._magic_status)

        v.addStretch()
        self._on_magic_template_changed()
        return w

    def _load_caption_rows(self):
        self._cap_table.setRowCount(0)
        for cap in self._clip.captions:
            self._insert_caption_row(
                float(cap.get("start", 0.0)),
                float(cap.get("end", min(self._clip.duration, 2.0))),
                str(cap.get("text", "Edit caption")),
                str(cap.get("font", "Bebas Neue")),
                str(cap.get("effect", "pop")),
            )

    def _insert_caption_row(self, start: float, end: float, text: str, font: str, effect: str):
        row = self._cap_table.rowCount()
        self._cap_table.insertRow(row)
        self._cap_table.setItem(row, 0, QTableWidgetItem(f"{max(0.0, start):.3f}"))
        self._cap_table.setItem(row, 1, QTableWidgetItem(f"{max(0.0, end):.3f}"))
        self._cap_table.setItem(row, 2, QTableWidgetItem(text))
        self._cap_table.setItem(row, 3, QTableWidgetItem(font))
        self._cap_table.setItem(row, 4, QTableWidgetItem(effect))

    def _add_caption_row(self):
        self._insert_caption_row(0.0, min(self._clip.duration, 2.0), "Edit caption", "Bebas Neue", "pop")

    def _remove_caption_row(self):
        row = self._cap_table.currentRow()
        if row >= 0:
            self._cap_table.removeRow(row)

    def _auto_detect_captions(self):
        if not self._source:
            return
        from god_factory_editor.core.effects_engine import effects_engine
        generated = effects_engine.generate_auto_captions_for_clip(
            self._source,
            self._clip,
            min_speech_seconds=0.6,
            font="Bebas Neue",
            effect="pop",
        )
        if not generated:
            return
        self._clip.captions = generated
        self._load_caption_rows()

    def _sync_preset_from_clip(self):
        """Reverse-match current clip audio values to a preset, or stay on 'none'."""
        for p in AUDIO_PRESETS:
            if (abs(p["voice_boost"] - self._clip.audio_voice_boost) < 0.5
                    and abs(p["game_duck"] - self._clip.audio_game_duck) < 0.5
                    and p["normalize"] == self._clip.audio_normalize
                    and p["denoise"] == self._clip.audio_denoise):
                idx = self._audio_preset_combo.findData(p["id"])
                if idx >= 0:
                    self._audio_preset_combo.blockSignals(True)
                    self._audio_preset_combo.setCurrentIndex(idx)
                    self._audio_preset_combo.blockSignals(False)
                    self._audio_desc_lbl.setText(p["description"])
                return

    def _on_magic_template_changed(self):
        tid = self._magic_combo.currentData()
        t = next((x for x in self._magic_templates if x["id"] == tid), None)
        if not t:
            self._magic_desc.setText("")
            return
        self._magic_desc.setText(t.get("description", ""))

    def _apply_magic_template(self):
        tid = self._magic_combo.currentData()
        adaptive = self._magic_adaptive_chk.isChecked()
        ok, msg = effects_engine.apply_magic_template(self._clip, tid, adaptive=adaptive)
        self._magic_status.setText(msg)
        self._magic_status.setStyleSheet("color:#3fb950; font-size:11px;" if ok else "color:#f85149; font-size:11px;")
        if not ok:
            return

        # Reflect template values immediately across existing controls.
        self._speed_spin.setValue(self._clip.speed)

        t_idx = self._trans_combo.findData(self._clip.transition_out)
        if t_idx >= 0:
            self._trans_combo.setCurrentIndex(t_idx)
        self._trans_dur_spin.setValue(self._clip.transition_duration)

        self._voice_boost_spin.setValue(self._clip.audio_voice_boost)
        self._game_duck_spin.setValue(self._clip.audio_game_duck)
        self._normalize_chk.setChecked(self._clip.audio_normalize)
        self._denoise_chk.setChecked(self._clip.audio_denoise)
        self._sync_preset_from_clip()

        self._brightness_spin.setValue(self._clip.picture_brightness)
        self._contrast_spin.setValue(self._clip.picture_contrast)
        self._saturation_spin.setValue(self._clip.picture_saturation)
        self._gamma_spin.setValue(self._clip.picture_gamma)
        self._sharpen_spin.setValue(self._clip.picture_sharpen)

    def _on_audio_preset_changed(self):
        pid = self._audio_preset_combo.currentData()
        for p in AUDIO_PRESETS:
            if p["id"] == pid:
                self._voice_boost_spin.setValue(p["voice_boost"])
                self._game_duck_spin.setValue(p["game_duck"])
                self._normalize_chk.setChecked(p["normalize"])
                self._denoise_chk.setChecked(p["denoise"])
                self._audio_desc_lbl.setText(p["description"])
                return

    def _run_analysis(self):
        if not self._source:
            return
        self._analyse_btn.setEnabled(False)
        self._analyse_prog.setVisible(True)
        self._analysis_result.setText("Analysing…")
        self._worker = _AnalysisWorker(self._source, self._clip)
        self._worker.done.connect(self._on_analysis_done)
        self._worker.start()

    def _on_analysis_done(self, result: dict):
        self._analyse_prog.setVisible(False)
        self._analyse_btn.setEnabled(True)
        lines = result.get("recommendations", [])
        suggested = result.get("suggested_preset", "none")
        text = "\n".join(f"• {l}" for l in lines)
        if suggested != "none":
            text += f"\n\n→ Suggested preset: <b>{suggested}</b>"
            idx = self._audio_preset_combo.findData(suggested)
            if idx >= 0:
                self._audio_preset_combo.setCurrentIndex(idx)
        self._analysis_result.setText(text)

    # ── Apply ─────────────────────────────────────────────────────────────────
    def _apply(self):
        self._clip.speed = self._speed_spin.value()
        self._clip.transition_out = self._trans_combo.currentData()
        self._clip.transition_duration = self._trans_dur_spin.value()
        self._clip.audio_voice_boost = self._voice_boost_spin.value()
        self._clip.audio_game_duck   = self._game_duck_spin.value()
        self._clip.audio_normalize   = self._normalize_chk.isChecked()
        self._clip.audio_denoise     = self._denoise_chk.isChecked()
        self._clip.picture_brightness = self._brightness_spin.value()
        self._clip.picture_contrast = self._contrast_spin.value()
        self._clip.picture_saturation = self._saturation_spin.value()
        self._clip.picture_gamma = self._gamma_spin.value()
        self._clip.picture_sharpen = self._sharpen_spin.value()

        captions = []
        for row in range(self._cap_table.rowCount()):
            item_start = self._cap_table.item(row, 0)
            item_end = self._cap_table.item(row, 1)
            if item_start is None or item_end is None:
                continue
            try:
                start = float(item_start.text().strip())
                end = float(item_end.text().strip())
            except ValueError:
                continue
            if end <= start:
                continue
            text_item = self._cap_table.item(row, 2)
            font_item = self._cap_table.item(row, 3)
            effect_item = self._cap_table.item(row, 4)
            captions.append(
                {
                    "start": max(0.0, min(start, self._clip.duration)),
                    "end": max(0.0, min(end, self._clip.duration)),
                    "text": (text_item.text().strip() if text_item else "Edit caption") or "Edit caption",
                    "font": (font_item.text().strip() if font_item else "Bebas Neue") or "Bebas Neue",
                    "effect": (effect_item.text().strip() if effect_item else "pop") or "pop",
                }
            )
        self._clip.captions = captions

        self.effects_applied.emit(self._clip.id)
        self.accept()

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt(seconds: float) -> str:
        s = max(0.0, seconds)
        m = int(s // 60)
        sc = s % 60
        return f"{m}:{sc:05.2f}"
