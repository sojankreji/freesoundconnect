"""Waveform display with playhead, click-to-seek and region selection."""

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

BG = QColor("#0e1126")
BORDER = QColor("#262c56")
WAVE = QColor("#4f9dff")
WAVE_PLAYED = QColor("#35e0c3")
SELECTION = QColor(53, 224, 195, 46)
SELECTION_EDGE = QColor("#35e0c3")
PLAYHEAD = QColor("#ffffff")
TEXT = QColor("#5c6289")

DRAG_THRESHOLD_PX = 5
BAR_WIDTH = 3.0
BAR_GAP = 2.0


class WaveformWidget(QWidget):
    """Draws min/max peaks. Click seeks; click-drag selects a region;
    double-click clears the selection."""

    seek_requested = Signal(float)       # fraction 0..1
    selection_changed = Signal(object)   # (start_frac, end_frac) or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._peaks = []
        self._message = "Select a sound to see its waveform"
        self._position = 0.0        # playhead fraction 0..1
        self._selection = None      # (start_frac, end_frac) or None
        self._press_x = None
        self._dragging = False

    # -- state ---------------------------------------------------------------

    def set_peaks(self, peaks):
        self._peaks = peaks or []
        self._message = "" if peaks else "No waveform available"
        self.update()

    def set_message(self, text):
        self._peaks = []
        self._message = text
        self.update()

    def set_position(self, fraction):
        self._position = min(1.0, max(0.0, fraction))
        self.update()

    def selection(self):
        return self._selection

    def clear_selection(self):
        if self._selection is not None:
            self._selection = None
            self.selection_changed.emit(None)
            self.update()

    def reset(self, message=None):
        self._position = 0.0
        self._selection = None
        self._peaks = []
        if message is not None:
            self._message = message
        self.selection_changed.emit(None)
        self.update()

    # -- mouse ---------------------------------------------------------------

    def _frac_at(self, x):
        w = max(1, self.width())
        return min(1.0, max(0.0, x / w))

    def mousePressEvent(self, event):  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton and self._peaks:
            self._press_x = event.position().x()
            self._dragging = False

    def mouseMoveEvent(self, event):  # noqa: N802 (Qt override)
        if self._press_x is None:
            return
        x = event.position().x()
        if not self._dragging and abs(x - self._press_x) < DRAG_THRESHOLD_PX:
            return
        self._dragging = True
        a, b = sorted((self._frac_at(self._press_x), self._frac_at(x)))
        self._selection = (a, b)
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802 (Qt override)
        if event.button() != Qt.MouseButton.LeftButton or self._press_x is None:
            return
        if self._dragging:
            self.selection_changed.emit(self._selection)
        else:
            self.seek_requested.emit(self._frac_at(event.position().x()))
        self._press_x = None
        self._dragging = False

    def mouseDoubleClickEvent(self, event):  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clear_selection()

    # -- painting ------------------------------------------------------------

    def paintEvent(self, _event):  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        painter.setPen(QPen(BORDER, 1))
        painter.setBrush(BG)
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 8, 8)

        if not self._peaks:
            if self._message:
                painter.setPen(TEXT)
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                                 self._message)
            return

        mid = h / 2.0
        amp = (h / 2.0) - 6
        played_x = self._position * w

        # Resample the stored peaks down to well-spaced bars so the shape
        # of the sound stays readable at any width.
        n_bars = max(16, int(w / (BAR_WIDTH + BAR_GAP)))
        n_peaks = len(self._peaks)
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(n_bars):
            lo_idx = i * n_peaks // n_bars
            hi_idx = max(lo_idx + 1, (i + 1) * n_peaks // n_bars)
            group = self._peaks[lo_idx:hi_idx]
            lo = min(p[0] for p in group)
            hi = max(p[1] for p in group)
            x = i * w / n_bars + BAR_GAP / 2
            top = mid - hi * amp
            height = (hi - lo) * amp
            if height < 2.0:
                top, height = mid - 1.0, 2.0
            painter.setBrush(
                WAVE_PLAYED if x + BAR_WIDTH / 2 <= played_x else WAVE)
            painter.drawRoundedRect(QRectF(x, top, BAR_WIDTH, height),
                                    1.5, 1.5)

        if self._selection:
            a, b = self._selection
            x1, x2 = a * w, b * w
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(SELECTION)
            painter.drawRect(QRectF(x1, 1, x2 - x1, h - 2))
            painter.setPen(QPen(SELECTION_EDGE, 1.5))
            painter.drawLine(QPointF(x1, 1), QPointF(x1, h - 2))
            painter.drawLine(QPointF(x2, 1), QPointF(x2, h - 2))

        painter.setPen(QPen(PLAYHEAD, 1.5))
        painter.drawLine(QPointF(played_x, 2), QPointF(played_x, h - 3))
