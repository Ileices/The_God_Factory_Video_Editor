from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from god_factory_editor.core.audio_enhancer import AUDIO_PRESETS
from god_factory_editor.core.automation_engine import AUTOMATION_PROFILES


class AutomationWizardDialog(QDialog):
    """One-click pipeline setup wizard for automation workflows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Automation Wizard")
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Choose a pipeline and tune thresholds once. The app will generate clips "
            "and apply retention/audio defaults automatically."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()

        self._profile = QComboBox()
        for p in AUTOMATION_PROFILES:
            self._profile.addItem(p["label"], p)
        self._profile.currentIndexChanged.connect(self._on_profile_changed)
        form.addRow("Pipeline:", self._profile)

        self._replace_existing = QCheckBox("Replace existing clip list")
        self._replace_existing.setChecked(True)
        form.addRow("", self._replace_existing)

        self._silence = QDoubleSpinBox()
        self._silence.setRange(1.0, 120.0)
        self._silence.setValue(10.0)
        self._silence.setSingleStep(0.5)
        self._silence.setSuffix(" s")
        form.addRow("Silence threshold:", self._silence)

        self._freeze = QDoubleSpinBox()
        self._freeze.setRange(0.5, 60.0)
        self._freeze.setValue(5.0)
        self._freeze.setSingleStep(0.5)
        self._freeze.setSuffix(" s")
        form.addRow("No-motion threshold:", self._freeze)

        self._black = QDoubleSpinBox()
        self._black.setRange(0.2, 30.0)
        self._black.setValue(1.5)
        self._black.setSingleStep(0.2)
        self._black.setSuffix(" s")
        form.addRow("Black/loading threshold:", self._black)

        self._min_keep = QDoubleSpinBox()
        self._min_keep.setRange(1.0, 300.0)
        self._min_keep.setValue(6.0)
        self._min_keep.setSingleStep(1.0)
        self._min_keep.setSuffix(" s")
        form.addRow("Minimum keep segment:", self._min_keep)

        self._max_clips = QSpinBox()
        self._max_clips.setRange(1, 500)
        self._max_clips.setValue(40)
        form.addRow("Max generated clips:", self._max_clips)

        self._decibel_gate = QDoubleSpinBox()
        self._decibel_gate.setRange(-60.0, -10.0)
        self._decibel_gate.setValue(-34.0)
        self._decibel_gate.setSingleStep(1.0)
        self._decibel_gate.setSuffix(" LUFS")
        form.addRow("Decibel gate (min loudness):", self._decibel_gate)

        self._noise_floor = QDoubleSpinBox()
        self._noise_floor.setRange(-70.0, -5.0)
        self._noise_floor.setValue(-38.0)
        self._noise_floor.setSingleStep(1.0)
        self._noise_floor.setSuffix(" dB")
        form.addRow("Silence noise floor:", self._noise_floor)

        self._voice_low = QSpinBox()
        self._voice_low.setRange(50, 1000)
        self._voice_low.setValue(180)
        self._voice_low.setSuffix(" Hz")
        form.addRow("Voice band low cutoff:", self._voice_low)

        self._voice_high = QSpinBox()
        self._voice_high.setRange(1000, 12000)
        self._voice_high.setValue(3400)
        self._voice_high.setSuffix(" Hz")
        form.addRow("Voice band high cutoff:", self._voice_high)

        self._voice_sensitivity = QDoubleSpinBox()
        self._voice_sensitivity.setRange(0.5, 3.0)
        self._voice_sensitivity.setSingleStep(0.1)
        self._voice_sensitivity.setValue(1.0)
        form.addRow("Voice sensitivity:", self._voice_sensitivity)

        self._short_target = QDoubleSpinBox()
        self._short_target.setRange(10.0, 120.0)
        self._short_target.setValue(45.0)
        self._short_target.setSingleStep(1.0)
        self._short_target.setSuffix(" s")
        form.addRow("Short target duration:", self._short_target)

        self._short_max = QDoubleSpinBox()
        self._short_max.setRange(15.0, 180.0)
        self._short_max.setValue(59.0)
        self._short_max.setSingleStep(1.0)
        self._short_max.setSuffix(" s")
        form.addRow("Short hard max duration:", self._short_max)

        self._captions = QCheckBox("Generate auto captions")
        self._captions.setChecked(True)
        form.addRow("", self._captions)

        self._transitions = QCheckBox("Apply retention transitions")
        self._transitions.setChecked(True)
        form.addRow("", self._transitions)

        self._sfx = QCheckBox("Apply retention SFX")
        self._sfx.setChecked(True)
        form.addRow("", self._sfx)

        self._audio_preset = QComboBox()
        for p in AUDIO_PRESETS:
            self._audio_preset.addItem(p["label"], p["id"])
        self._audio_preset.setCurrentIndex(max(0, self._audio_preset.findData("voice_boost_light")))
        form.addRow("Audio cleanup preset:", self._audio_preset)

        root.addLayout(form)

        self._description = QLabel("")
        self._description.setWordWrap(True)
        root.addWidget(self._description)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._on_profile_changed()

    def _on_profile_changed(self):
        p = self._profile.currentData() or {}
        pid = p.get("id", "stream_highlights")
        self._description.setText(p.get("description", ""))

        shorts_mode = pid == "stream_shorts"
        audio_mode = pid == "audio_cleanup"

        self._short_target.setEnabled(shorts_mode)
        self._short_max.setEnabled(shorts_mode)
        self._transitions.setEnabled(not audio_mode)
        self._sfx.setEnabled(not audio_mode)
        self._captions.setEnabled(not audio_mode)
        self._audio_preset.setEnabled(audio_mode)

    def values(self) -> dict:
        p = self._profile.currentData() or {}
        return {
            "profile_id": p.get("id", "stream_highlights"),
            "replace_existing": self._replace_existing.isChecked(),
            "silence_seconds": self._silence.value(),
            "freeze_seconds": self._freeze.value(),
            "black_seconds": self._black.value(),
            "min_keep_seconds": self._min_keep.value(),
            "max_clips": self._max_clips.value(),
            "decibel_gate_lufs": self._decibel_gate.value(),
            "noise_floor_db": self._noise_floor.value(),
            "voice_band_low_hz": self._voice_low.value(),
            "voice_band_high_hz": self._voice_high.value(),
            "voice_sensitivity": self._voice_sensitivity.value(),
            "short_target_seconds": self._short_target.value(),
            "short_max_seconds": self._short_max.value(),
            "generate_captions": self._captions.isChecked(),
            "apply_transitions": self._transitions.isChecked(),
            "apply_sfx": self._sfx.isChecked(),
            "audio_preset_id": self._audio_preset.currentData() or "voice_boost_light",
        }
