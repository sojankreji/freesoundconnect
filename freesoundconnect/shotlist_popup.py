"""Shotlist "cart" popup, anchored under the header's shotlist button."""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
    QPushButton, QVBoxLayout,
)

from .results_tree import COMPACT_COLUMNS, ResultsTree

POPUP_WIDTH = 420
POPUP_HEIGHT = 440


class ShotlistPopup(QDialog):
    """Cart-like review screen for the shotlist: preview, drag to Resolve,
    remove items, or save the whole list as a named playlist."""

    sound_selected = Signal(object)
    sound_activated = Signal(object)
    status_message = Signal(str)

    def __init__(self, store, ensure_local_file, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowFlags(Qt.WindowType.Tool |
                            Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(POPUP_WIDTH, POPUP_HEIGHT)

        frame = QFrame()
        frame.setObjectName("PopupFrame")

        title = QLabel("🛒  Shotlist")
        title.setObjectName("PanelTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("Hint")
        close_btn = QPushButton("✕")
        close_btn.setObjectName("LogoutButton")
        close_btn.clicked.connect(self.hide)

        header = QHBoxLayout()
        header.addWidget(title)
        header.addWidget(self.count_label)
        header.addStretch(1)
        header.addWidget(close_btn)

        self.tree = ResultsTree(ensure_local_file, columns=COMPACT_COLUMNS)
        self.tree.currentItemChanged.connect(
            lambda *_: self._emit_current(self.sound_selected))
        self.tree.itemDoubleClicked.connect(
            lambda *_: self._emit_current(self.sound_activated))

        hint = QLabel("Drag a row straight onto your Resolve timeline. "
                      "Double-click to preview.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)

        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("SmallButton")
        remove_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("SmallButton")
        clear_btn.clicked.connect(self._clear)
        save_btn = QPushButton("Save as playlist…")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._save_as_playlist)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.addWidget(remove_btn)
        actions.addWidget(clear_btn)
        actions.addStretch(1)
        actions.addWidget(save_btn)

        inner = QVBoxLayout(frame)
        inner.setContentsMargins(12, 10, 12, 12)
        inner.setSpacing(8)
        inner.addLayout(header)
        inner.addWidget(self.tree, 1)
        inner.addWidget(hint)
        inner.addLayout(actions)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

        self.store.changed.connect(self.refresh)
        self.refresh()

    def _emit_current(self, signal):
        sound = self.tree.current_sound()
        if sound:
            signal.emit(sound)

    def toggle_below(self, button):
        if self.isVisible():
            self.hide()
            return
        corner = button.mapToGlobal(QPoint(button.width(), button.height()))
        self.move(corner - QPoint(self.width(), -8))
        self.show()
        self.raise_()

    def refresh(self):
        sounds = self.store.shotlist()
        self.tree.set_sounds(sounds)
        self.count_label.setText(
            "· %d sound%s" % (len(sounds), "" if len(sounds) == 1 else "s")
            if sounds else "· empty")

    def _remove_selected(self):
        sound = self.tree.current_sound()
        if sound:
            self.store.remove_from_shotlist(sound["id"])

    def _clear(self):
        if not self.store.shotlist():
            return
        if QMessageBox.question(
                self, "Clear shotlist",
                "Remove all sounds from the shotlist?") == \
                QMessageBox.StandardButton.Yes:
            self.store.clear_shotlist()

    def _save_as_playlist(self):
        sounds = self.store.shotlist()
        if not sounds:
            self.status_message.emit("The shotlist is empty — add some "
                                     "sounds first.")
            return
        name, ok = QInputDialog.getText(self, "Save playlist",
                                        "Playlist name:")
        name = (name or "").strip()
        if not ok or not name:
            return
        if self.store.has_playlist(name) and QMessageBox.question(
                self, "Overwrite playlist",
                "A playlist named “%s” already exists. Overwrite it?"
                % name) != QMessageBox.StandardButton.Yes:
            return
        self.store.save_playlist(name, sounds)
        self.status_message.emit("Saved playlist “%s” (%d sounds)." %
                                 (name, len(sounds)))
