"""Playlists page: browse saved playlists and manage their sounds."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from .results_tree import FULL_COLUMNS, ResultsTree


class PlaylistsPage(QWidget):
    sound_selected = Signal(object)
    sound_activated = Signal(object)
    status_message = Signal(str)

    def __init__(self, store, ensure_local_file, parent=None):
        super().__init__(parent)
        self.store = store

        # Left: playlist names
        names_title = QLabel("Playlists")
        names_title.setObjectName("PanelTitle")

        self.names_list = QListWidget()
        self.names_list.currentRowChanged.connect(lambda *_: self._show_selected())

        rename_btn = QPushButton("Rename…")
        rename_btn.setObjectName("SmallButton")
        rename_btn.clicked.connect(self._rename_playlist)
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("SmallButton")
        delete_btn.clicked.connect(self._delete_playlist)

        name_actions = QHBoxLayout()
        name_actions.setSpacing(6)
        name_actions.addWidget(rename_btn)
        name_actions.addStretch(1)
        name_actions.addWidget(delete_btn)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(names_title)
        left_layout.addWidget(self.names_list, 1)
        left_layout.addLayout(name_actions)

        # Right: the selected playlist's sounds
        self.sounds_title = QLabel("")
        self.sounds_title.setObjectName("PanelTitle")

        self.tree = ResultsTree(ensure_local_file, columns=FULL_COLUMNS)
        self.tree.currentItemChanged.connect(
            lambda *_: self._emit_current(self.sound_selected))
        self.tree.itemDoubleClicked.connect(
            lambda *_: self._emit_current(self.sound_activated))

        to_shotlist_btn = QPushButton("＋ Add to Shotlist")
        to_shotlist_btn.setObjectName("SmallButton")
        to_shotlist_btn.clicked.connect(self._add_to_shotlist)
        remove_btn = QPushButton("Remove from playlist")
        remove_btn.setObjectName("SmallButton")
        remove_btn.clicked.connect(self._remove_sound)

        sound_actions = QHBoxLayout()
        sound_actions.setSpacing(6)
        sound_actions.addWidget(to_shotlist_btn)
        sound_actions.addStretch(1)
        sound_actions.addWidget(remove_btn)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.addWidget(self.sounds_title)
        right_layout.addWidget(self.tree, 1)
        right_layout.addLayout(sound_actions)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(left)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([230, 700])

        self.empty_hint = QLabel(
            "No playlists yet.\n\nCollect sounds in the shotlist (🛒 top "
            "right) and use “Save as playlist…” to create one.")
        self.empty_hint.setObjectName("Hint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.empty_hint, 1)
        layout.addWidget(self.splitter, 1)

        self.store.changed.connect(self.refresh)
        self.refresh()

    # -- helpers -------------------------------------------------------------

    def _emit_current(self, signal):
        sound = self.tree.current_sound()
        if sound:
            signal.emit(sound)

    def current_playlist_name(self):
        item = self.names_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # -- refresh -------------------------------------------------------------

    def refresh(self):
        selected = self.current_playlist_name()
        playlists = self.store.playlists()

        self.empty_hint.setVisible(not playlists)
        self.splitter.setVisible(bool(playlists))

        self.names_list.blockSignals(True)
        self.names_list.clear()
        names = sorted(playlists)
        for name in names:
            self.names_list.addItem("%s  (%d)" % (name, len(playlists[name])))
            item = self.names_list.item(self.names_list.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, name)
        self.names_list.blockSignals(False)

        if names:
            row = names.index(selected) if selected in names else 0
            self.names_list.setCurrentRow(row)
        self._show_selected()

    def _show_selected(self):
        name = self.current_playlist_name()
        if not name:
            self.sounds_title.setText("")
            self.tree.set_sounds([])
            return
        sounds = self.store.playlist(name)
        self.sounds_title.setText("%s — %d sound%s" % (
            name, len(sounds), "" if len(sounds) == 1 else "s"))
        self.tree.set_sounds(sounds)

    # -- actions -------------------------------------------------------------

    def _rename_playlist(self):
        old = self.current_playlist_name()
        if not old:
            return
        new, ok = QInputDialog.getText(self, "Rename playlist",
                                       "New name:", text=old)
        new = (new or "").strip()
        if not ok or not new or new == old:
            return
        if not self.store.rename_playlist(old, new):
            self.status_message.emit(
                "A playlist named “%s” already exists." % new)
            return
        self.status_message.emit("Renamed “%s” to “%s”." % (old, new))

    def _delete_playlist(self):
        name = self.current_playlist_name()
        if not name:
            return
        if QMessageBox.question(
                self, "Delete playlist",
                "Delete the playlist “%s”? (The shotlist is not affected.)"
                % name) != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_playlist(name)
        self.status_message.emit("Deleted playlist “%s”." % name)

    def _add_to_shotlist(self):
        sound = self.tree.current_sound()
        if not sound:
            self.status_message.emit("Select a sound first.")
            return
        if self.store.add_to_shotlist(sound):
            self.status_message.emit("Added “%s” to the shotlist." %
                                     sound.get("name"))
        else:
            self.status_message.emit("“%s” is already in the shotlist." %
                                     sound.get("name"))

    def _remove_sound(self):
        name = self.current_playlist_name()
        sound = self.tree.current_sound()
        if not name or not sound:
            self.status_message.emit("Select a sound first.")
            return
        self.store.remove_from_playlist(name, sound["id"])
        self.status_message.emit("Removed “%s” from “%s”." %
                                 (sound.get("name"), name))
