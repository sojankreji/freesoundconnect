"""Audio decoding (via QtMultimedia), waveform peaks and region export."""

import array
import os
import wave

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat

from .api import FreesoundError

WAVEFORM_BINS = 800


class DecodedAudio:
    def __init__(self, samples, rate, channels):
        self.samples = samples  # array('h'), interleaved int16
        self.rate = rate
        self.channels = channels

    @property
    def frame_count(self):
        return len(self.samples) // max(1, self.channels)

    @property
    def duration(self):
        return self.frame_count / float(self.rate) if self.rate else 0.0


def decode_file(path, timeout_ms=120000):
    """Decode any Qt-supported audio file to interleaved int16 PCM.

    Blocking: spins a local QEventLoop until the decoder finishes, so it is
    safe both on the UI thread (short files, with a wait cursor) and inside
    a QThread.run().
    """
    fmt = QAudioFormat()
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

    decoder = QAudioDecoder()
    decoder.setAudioFormat(fmt)
    decoder.setSource(QUrl.fromLocalFile(path))

    chunks = []
    state = {"rate": 0, "channels": 0, "error": None}
    loop = QEventLoop()

    def on_buffer_ready():
        buf = decoder.read()
        if not buf.isValid():
            return
        bfmt = buf.format()
        state["rate"] = bfmt.sampleRate()
        state["channels"] = bfmt.channelCount()
        chunks.append(bytes(buf.data()))

    def on_error(*_args):
        state["error"] = decoder.errorString() or "decode error"
        loop.quit()

    decoder.bufferReady.connect(on_buffer_ready)
    decoder.finished.connect(loop.quit)
    decoder.error.connect(on_error)

    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(loop.quit)
    watchdog.start(timeout_ms)

    decoder.start()
    loop.exec()
    decoder.stop()

    if state["error"]:
        raise FreesoundError("Could not decode audio: %s" % state["error"])
    if not chunks or not state["rate"]:
        raise FreesoundError("Could not decode audio (no data).")

    samples = array.array("h")
    for chunk in chunks:
        samples.frombytes(chunk[: len(chunk) - (len(chunk) % 2)])
    return DecodedAudio(samples, state["rate"], state["channels"] or 1)


def compute_peaks(decoded, bins=WAVEFORM_BINS):
    """Reduce PCM to per-bin (min, max) pairs normalized to -1..1."""
    channels = max(1, decoded.channels)
    frames = decoded.frame_count
    if frames == 0:
        return []
    bins = min(bins, frames)
    peaks = []
    samples = decoded.samples
    for i in range(bins):
        start = (i * frames // bins) * channels
        end = ((i + 1) * frames // bins) * channels
        seg = samples[start:end]
        if not seg:
            peaks.append((0.0, 0.0))
            continue
        peaks.append((min(seg) / 32768.0, max(seg) / 32768.0))
    return peaks


def write_wav_region(decoded, start_s, end_s, dest):
    """Write [start_s, end_s) of the decoded PCM as a 16-bit WAV file."""
    channels = max(1, decoded.channels)
    start_f = max(0, min(decoded.frame_count, int(start_s * decoded.rate)))
    end_f = max(start_f, min(decoded.frame_count, int(end_s * decoded.rate)))
    if end_f - start_f < 1:
        raise FreesoundError("Selection is too short to export.")
    segment = decoded.samples[start_f * channels:end_f * channels]
    tmp = dest + ".part"
    with wave.open(tmp, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(decoded.rate)
        out.writeframes(segment.tobytes())
    os.replace(tmp, dest)
    return dest
