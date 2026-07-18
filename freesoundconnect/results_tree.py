"""Draggable sound list used for both search results and the shotlist."""

from PySide6.QtCore import QMimeData, Qt, QUrl
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QTreeWidget, QTreeWidgetItem,
)

from .api import (
    format_duration, format_rating, format_specs, short_license,
    sound_tooltip,
)

FULL_COLUMNS = ["Name", "Duration", "Type", "Specs", "Rating", "Downloads",
                "Author", "License"]
COMPACT_COLUMNS = ["Name", "Duration", "Author"]


def make_sound_item(sound, columns):
    values = {
        "Name": sound.get("name", ""),
        "Duration": format_duration(sound.get("duration", 0)),
        "Type": (sound.get("type") or "").upper(),
        "Specs": format_specs(sound),
        "Rating": format_rating(sound),
        "Downloads": str(sound.get("num_downloads") or ""),
        "Author": sound.get("username", ""),
        "License": short_license(sound.get("license", "")),
    }
    item = QTreeWidgetItem([values[c] for c in columns])
    item.setData(0, Qt.ItemDataRole.UserRole, sound)
    tooltip = sound_tooltip(sound)
    for col in range(len(columns)):
        item.setToolTip(col, tooltip)
    return item


class ResultsTree(QTreeWidget):
    """Rows can be dragged out of the app as real audio files — drop them
    on Resolve's timeline or Media Pool (or any other app). If a waveform
    region is selected, only that region is exported and dragged."""

    def __init__(self, ensure_local_file, columns=None, parent=None):
        super().__init__(parent)
        self._ensure_local_file = ensure_local_file
        self._columns = columns or FULL_COLUMNS
        self.setDragEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(True)
        self.setHeaderLabels(self._columns)
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(self._columns)):
            header.setSectionResizeMode(col,
                                        QHeaderView.ResizeMode.ResizeToContents)

    def set_sounds(self, sounds):
        self.clear()
        for sound in sounds:
            self.addTopLevelItem(make_sound_item(sound, self._columns))

    def current_sound(self):
        item = self.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def startDrag(self, supported_actions):  # noqa: N802 (Qt override)
        sound = self.current_sound()
        if not sound:
            return
        path = self._ensure_local_file(sound)
        if not path:
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)
