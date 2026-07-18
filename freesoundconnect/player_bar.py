"""Playback bar: waveform, transport controls, seek, volume, selection."""

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout,
)

from .api import format_duration, preview_url
from .waveform import WaveformWidget
from .workers import WaveformWorker


class PlayerBar(QFrame):
    """Owns the QMediaPlayer. Streams the sound's preview for playback and
    shows a decoded waveform where the user can seek and select the region
    to insert into the timeline."""

    status_message = Signal(str)
    worker_started = Signal(object)  # QThread, for lifetime tracking

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlayerBar")
        self.sound = None
        self.preview_audio = None  # DecodedAudio of the preview, for trimming
        self._duration_s = 0.0

        self.audio_out = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_out)
        self.player.errorOccurred.connect(self._on_player_error)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

        self.title_label = QLabel("No sound loaded")
        self.title_label.setObjectName("PanelTitle")

        self.selection_label = QLabel("")
        self.selection_label.setObjectName("SelectionLabel")
        self.clear_sel_btn = QPushButton("Clear selection")
        self.clear_sel_btn.setObjectName("SmallButton")
        self.clear_sel_btn.clicked.connect(self._clear_selection)
        self.clear_sel_btn.hide()

        top = QHBoxLayout()
        top.addWidget(self.title_label, 1)
        top.addWidget(self.selection_label)
        top.addWidget(self.clear_sel_btn)

        self.waveform = WaveformWidget()
        self.waveform.seek_requested.connect(self._on_seek_requested)
        self.waveform.selection_changed.connect(self._on_selection_changed)

        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("TransportButton")
        self.play_btn.setToolTip("Play / pause (selection plays as a loop "
                                 "region)")
        self.play_btn.clicked.connect(self.toggle_play)
        self.stop_btn = QPushButton("■")
        self.stop_btn.setObjectName("TransportButton")
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self.stop)

        self.time_label = QLabel("0:00.00 / 0:00.00")
        self.time_label.setObjectName("TimeLabel")

        vol_icon = QLabel("🔊")
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setFixedWidth(110)
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        self.volume.valueChanged.connect(
            lambda v: self.audio_out.setVolume(v / 100.0))
        self.audio_out.setVolume(0.8)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.time_label)
        controls.addStretch(1)
        hint = QLabel("Drag on the waveform to choose the part to insert")
        hint.setObjectName("Hint")
        controls.addWidget(hint)
        controls.addStretch(1)
        controls.addWidget(vol_icon)
        controls.addWidget(self.volume)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        layout.addLayout(top)
        layout.addWidget(self.waveform, 1)
        layout.addLayout(controls)

    # -- loading -------------------------------------------------------------

    def load_sound(self, sound):
        if sound is None or (self.sound and sound["id"] == self.sound["id"]):
            return
        self.stop()
        self.sound = sound
        self.preview_audio = None
        self._duration_s = float(sound.get("duration") or 0.0)
        self.title_label.setText(sound.get("name", ""))
        self.waveform.reset("Loading waveform…")
        self._update_time_label(0)

        try:
            self.player.setSource(QUrl(preview_url(sound)))
        except Exception:  # noqa: BLE001 - sound without preview
            self.waveform.set_message("No preview available")
            return

        worker = WaveformWorker(sound)
        worker.succeeded.connect(self._on_waveform_ready)
        worker.failed.connect(self._on_waveform_failed)
        self.worker_started.emit(worker)
        worker.start()

    def _on_waveform_ready(self, sound_id, peaks, decoded):
        if not self.sound or self.sound["id"] != sound_id:
            return
        self.waveform.set_peaks(peaks)
        self.preview_audio = decoded
        if decoded.duration:
            self._duration_s = decoded.duration
        # Once cached locally, play the decoded file rather than streaming.
        if self.player.playbackState() == \
                QMediaPlayer.PlaybackState.StoppedState:
            self.player.setSource(
                QUrl.fromLocalFile(WaveformWorker.cache_path(self.sound)))

    def _on_waveform_failed(self, sound_id, message):
        if not self.sound or self.sound["id"] != sound_id:
            return
        self.waveform.set_message("Waveform unavailable")
        self.status_message.emit(message)

    # -- transport -----------------------------------------------------------

    def toggle_play(self):
        if not self.sound:
            self.status_message.emit("Select a sound first.")
            return
        if self.player.playbackState() == \
                QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            return
        sel = self.selection_seconds()
        if sel:
            pos_s = self.player.position() / 1000.0
            if pos_s < sel[0] or pos_s >= sel[1] - 0.01:
                self.player.setPosition(int(sel[0] * 1000))
        self.player.play()

    def play_sound(self, sound):
        self.load_sound(sound)
        if self.sound:
            self.player.stop()
            self.player.play()
            self.status_message.emit("Playing: %s" % self.sound["name"])

    def stop(self):
        self.player.stop()

    # -- selection -----------------------------------------------------------

    def selection_seconds(self):
        """Current waveform selection as (start_s, end_s), or None."""
        sel = self.waveform.selection()
        if not sel or not self._duration_s:
            return None
        start_s = sel[0] * self._duration_s
        end_s = sel[1] * self._duration_s
        if end_s - start_s < 0.05:
            return None
        return (start_s, end_s)

    def _clear_selection(self):
        self.waveform.clear_selection()

    def _on_selection_changed(self, _sel):
        sel = self.selection_seconds()
        if sel:
            self.selection_label.setText(
                "Selection: %s – %s  (drag the row to insert just this part)"
                % (format_duration(sel[0]), format_duration(sel[1])))
            self.clear_sel_btn.show()
        else:
            self.selection_label.setText("")
            self.clear_sel_btn.hide()

    # -- player events -------------------------------------------------------

    def _on_seek_requested(self, fraction):
        if not self.sound:
            return
        duration_ms = self.player.duration() or int(self._duration_s * 1000)
        self.player.setPosition(int(fraction * duration_ms))

    def _on_position_changed(self, pos_ms):
        duration_ms = self.player.duration() or int(self._duration_s * 1000)
        if duration_ms > 0:
            self.waveform.set_position(pos_ms / duration_ms)
        self._update_time_label(pos_ms)
        sel = self.selection_seconds()
        if (sel and self.player.playbackState() ==
                QMediaPlayer.PlaybackState.PlayingState
                and pos_ms >= int(sel[1] * 1000)):
            self.player.pause()
            self.player.setPosition(int(sel[0] * 1000))

    def _update_time_label(self, pos_ms):
        self.time_label.setText("%s / %s" % (
            format_duration(pos_ms / 1000.0),
            format_duration(self._duration_s)))

    def _on_state_changed(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_btn.setText("⏸" if playing else "▶")

    def _on_player_error(self, _error, message):
        if message:
            self.status_message.emit("Playback error: %s" % message)
