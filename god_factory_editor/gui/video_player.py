"""
VideoPlayer widget — wraps PySide6 QMediaPlayer + QVideoWidget.
Handles play/pause, seeking, loop regions, and volume.
Emits signals consumed by the timeline and status bar.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider,
    QPushButton, QLabel, QSizePolicy,
)

from god_factory_editor.utils.time_utils import seconds_to_str, clamp
from god_factory_editor.utils.logger import log


class VideoPlayer(QWidget):
    """
    Signals
    -------
    position_changed(seconds)      — playhead moved (50 ms poll)
    duration_changed(seconds)      — new media loaded
    playback_state_changed(playing)
    media_loaded()
    media_error(message)
    """

    position_changed = Signal(float)
    duration_changed = Signal(float)
    playback_state_changed = Signal(bool)
    media_loaded = Signal()
    media_error = Signal(str)

    POLL_MS = 80  # how often to poll playhead position

    def __init__(self, parent=None):
        super().__init__(parent)
        self._duration: float = 0.0
        self._loop_start: Optional[float] = None
        self._loop_end: Optional[float] = None
        self._source_path: Optional[Path] = None
        self._seeking = False
        self._last_pos: float = 0.0

        self._build_ui()
        self._setup_player()
        self._connect_signals()

        # Position poll timer
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.POLL_MS)
        self._poll_timer.timeout.connect(self._poll_position)
        self._poll_timer.start()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Video surface
        self._video_widget = QVideoWidget()
        self._video_widget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._video_widget.setMinimumHeight(200)
        layout.addWidget(self._video_widget, 1)

        # Progress/seek slider
        self._seek_slider = QSlider(Qt.Horizontal)
        self._seek_slider.setRange(0, 10000)
        self._seek_slider.setObjectName("seekSlider")
        layout.addWidget(self._seek_slider)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(4, 0, 4, 0)

        self._play_btn = QPushButton("Play")
        self._play_btn.setFixedWidth(44)
        self._play_btn.setObjectName("playBtn")
        ctrl.addWidget(self._play_btn)

        self._time_lbl = QLabel("00:00 / 00:00")
        self._time_lbl.setObjectName("timeLabel")
        ctrl.addWidget(self._time_lbl)

        ctrl.addStretch()

        # Volume
        vol_lbl = QLabel("Vol")
        ctrl.addWidget(vol_lbl)
        self._vol_slider = QSlider(Qt.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setFixedWidth(90)
        self._vol_slider.setObjectName("volSlider")
        ctrl.addWidget(self._vol_slider)

        layout.addLayout(ctrl)

    # ── Setup QMediaPlayer ────────────────────────────────────────────────────
    def _setup_player(self):
        self._audio = QAudioOutput()
        self._audio.setVolume(0.8)

        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_widget)

    def _connect_signals(self):
        self._play_btn.clicked.connect(self.toggle_play)
        self._seek_slider.sliderPressed.connect(self._on_slider_press)
        self._seek_slider.sliderReleased.connect(self._on_slider_release)
        self._seek_slider.sliderMoved.connect(self._on_slider_moved)
        self._vol_slider.valueChanged.connect(self._on_volume_changed)

        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.errorOccurred.connect(self._on_error)

    # ── Public API ────────────────────────────────────────────────────────────
    def load(self, path: Path):
        """Load a video file (or proxy)."""
        self._source_path = Path(path)
        url = QUrl.fromLocalFile(str(path))
        self._player.setSource(url)
        log.info(f"VideoPlayer: loaded {path.name}")

    @property
    def source_path(self) -> Optional[Path]:
        return self._source_path

    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self.pause()
        else:
            self.play()

    def seek(self, seconds: float):
        """Seek to a position in seconds."""
        seconds = clamp(seconds, 0.0, self._duration)
        ms = int(seconds * 1000)
        self._player.setPosition(ms)
        self._last_pos = seconds
        self.position_changed.emit(seconds)

    def current_position(self) -> float:
        return self._player.position() / 1000.0

    @property
    def duration(self) -> float:
        return self._duration

    def set_volume(self, volume: float):
        """Volume 0.0–1.0"""
        self._audio.setVolume(clamp(volume, 0.0, 1.0))
        self._vol_slider.setValue(int(volume * 100))

    # ── Aliases / extras expected by main_window ─────────────────────────────
    def toggle_playback(self):
        """Alias for toggle_play — called by control panel actions."""
        self.toggle_play()

    def seek_relative(self, delta: float):
        """Seek forward/backward by delta seconds."""
        self.seek(self.current_position() + delta)

    def stop(self):
        """Stop playback and return to start."""
        self._player.stop()
        self.seek(0.0)

    def set_loop(self, start: float, end: float):
        self._loop_start = start
        self._loop_end = end

    def clear_loop(self):
        self._loop_start = None
        self._loop_end = None

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlayingState

    # ── Slots ─────────────────────────────────────────────────────────────────
    def _on_duration_changed(self, ms: int):
        self._duration = ms / 1000.0
        self._seek_slider.setRange(0, max(1, ms))
        self._update_time_label(0)
        self.duration_changed.emit(self._duration)
        self.media_loaded.emit()
        log.debug(f"Duration: {self._duration:.1f}s")

    def _on_state_changed(self, state):
        playing = state == QMediaPlayer.PlayingState
        self._play_btn.setText("Pause" if playing else "Play")
        self.playback_state_changed.emit(playing)

    def _on_error(self, error, error_string: str):
        msg = f"Playback error: {error_string}"
        log.error(msg)
        self.media_error.emit(msg)

    def _on_slider_press(self):
        self._seeking = True

    def _on_slider_release(self):
        self._seeking = False
        pos_ms = self._seek_slider.value()
        self._player.setPosition(pos_ms)

    def _on_slider_moved(self, value: int):
        seconds = value / 1000.0
        self._update_time_label(seconds)
        self.position_changed.emit(seconds)

    def _on_volume_changed(self, value: int):
        self._audio.setVolume(value / 100.0)

    def _poll_position(self):
        if self._seeking:
            return
        pos_ms = self._player.position()
        seconds = pos_ms / 1000.0

        if abs(seconds - self._last_pos) > 0.05:
            self._last_pos = seconds
            self._seek_slider.setValue(pos_ms)
            self._update_time_label(seconds)
            self.position_changed.emit(seconds)

        # Loop region
        if (self._loop_end is not None and
                self._loop_start is not None and
                self.is_playing() and
                seconds >= self._loop_end):
            self.seek(self._loop_start)

    def _update_time_label(self, current: float):
        self._time_lbl.setText(
            f"{seconds_to_str(current)} / {seconds_to_str(self._duration)}"
        )

    # ── Keyboard ──────────────────────────────────────────────────────────────
    def keyPressEvent(self, event):
        from PySide6.QtCore import Qt as _Qt
        key = event.key()
        mods = event.modifiers()
        step = 30.0 if mods & _Qt.ShiftModifier else 5.0
        if key == _Qt.Key_Left:
            self.seek(self.current_position() - step)
        elif key == _Qt.Key_Right:
            self.seek(self.current_position() + step)
        elif key == _Qt.Key_Space:
            self.toggle_play()
        else:
            super().keyPressEvent(event)
