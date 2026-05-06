from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QCheckBox,
    QDialogButtonBox,
    QLabel,
)

from god_factory_editor.core.effects_engine import AUTO_EDIT_TEMPLATES


class AutoEditDialog(QDialog):
    """Fine-tuning dialog for boring-part auto edit and retention rules."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Auto-Edit Boring Parts")
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)

        intro = QLabel(
            "Tune what counts as boring, choose remove vs fast-forward behavior, "
            "and apply retention rules (transitions, SFX, optional slow-mo hints, captions)."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()

        self._template = QComboBox()
        for t in AUTO_EDIT_TEMPLATES:
            self._template.addItem(t["label"], t)
        self._template.currentIndexChanged.connect(self._apply_template)
        form.addRow("Template:", self._template)

        self._silence = QDoubleSpinBox()
        self._silence.setRange(1.0, 120.0)
        self._silence.setSingleStep(0.5)
        self._silence.setSuffix(" s")
        form.addRow("Silence threshold:", self._silence)

        self._freeze = QDoubleSpinBox()
        self._freeze.setRange(0.5, 60.0)
        self._freeze.setSingleStep(0.5)
        self._freeze.setSuffix(" s")
        form.addRow("No-motion threshold:", self._freeze)

        self._black = QDoubleSpinBox()
        self._black.setRange(0.2, 30.0)
        self._black.setSingleStep(0.2)
        self._black.setSuffix(" s")
        form.addRow("Black/loading threshold:", self._black)

        self._min_keep = QDoubleSpinBox()
        self._min_keep.setRange(0.5, 120.0)
        self._min_keep.setSingleStep(0.5)
        self._min_keep.setSuffix(" s")
        form.addRow("Minimum keep segment:", self._min_keep)

        self._action = QComboBox()
        self._action.addItem("Remove boring portions", "remove")
        self._action.addItem("Fast-forward boring portions", "speedup")
        form.addRow("Behavior:", self._action)

        self._speed = QDoubleSpinBox()
        self._speed.setRange(1.5, 64.0)
        self._speed.setSingleStep(0.5)
        self._speed.setSuffix("×")
        form.addRow("Fast-forward speed:", self._speed)

        self._transition_len = QDoubleSpinBox()
        self._transition_len.setRange(2.0, 300.0)
        self._transition_len.setSingleStep(1.0)
        self._transition_len.setSuffix(" s")
        form.addRow("Transition min clip length:", self._transition_len)

        self._caption_min = QDoubleSpinBox()
        self._caption_min.setRange(0.2, 10.0)
        self._caption_min.setSingleStep(0.1)
        self._caption_min.setSuffix(" s")
        form.addRow("Caption min speech segment:", self._caption_min)

        self._apply_transitions = QCheckBox("Auto-apply transitions")
        self._apply_transitions.setChecked(True)
        form.addRow("", self._apply_transitions)

        self._apply_sfx = QCheckBox("Auto-apply sound effects")
        self._apply_sfx.setChecked(True)
        form.addRow("", self._apply_sfx)

        self._imply_slowmo = QCheckBox("Imply slow-mo for short intense keeps")
        self._imply_slowmo.setChecked(False)
        form.addRow("", self._imply_slowmo)

        self._auto_captions = QCheckBox("Generate editable auto-captions (speech-region based)")
        self._auto_captions.setChecked(True)
        form.addRow("", self._auto_captions)

        root.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._apply_template()

    def _apply_template(self):
        t = self._template.currentData()
        if not t:
            return
        self._silence.setValue(float(t.get("silence_seconds", 10.0)))
        self._freeze.setValue(float(t.get("freeze_seconds", 5.0)))
        self._black.setValue(float(t.get("black_seconds", 1.5)))
        self._min_keep.setValue(float(t.get("min_keep_seconds", 6.0)))
        self._action.setCurrentIndex(max(0, self._action.findData(t.get("action", "remove"))))
        self._speed.setValue(float(t.get("speed_factor", 8.0)))
        self._transition_len.setValue(float(t.get("transition_min_clip_seconds", 20.0)))
        self._caption_min.setValue(float(t.get("caption_min_speech_seconds", 0.8)))

    def values(self) -> dict:
        return {
            "template_id": (self._template.currentData() or {}).get("id", "balanced"),
            "silence_seconds": self._silence.value(),
            "freeze_seconds": self._freeze.value(),
            "black_seconds": self._black.value(),
            "min_keep_seconds": self._min_keep.value(),
            "action": self._action.currentData(),
            "speed_factor": self._speed.value(),
            "transition_min_clip_seconds": self._transition_len.value(),
            "caption_min_speech_seconds": self._caption_min.value(),
            "apply_transitions": self._apply_transitions.isChecked(),
            "apply_sfx": self._apply_sfx.isChecked(),
            "imply_slowmo": self._imply_slowmo.isChecked(),
            "auto_captions": self._auto_captions.isChecked(),
        }
