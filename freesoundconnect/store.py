"""Shared shotlist/playlist data store.

Single source of truth used by the shotlist popup, the playlists sidebar
and the cart button — every mutation persists to disk and emits changed().
"""

from PySide6.QtCore import QObject, Signal

from .config import load_playlists, save_playlists


class PlaylistStore(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = load_playlists()

    # -- shotlist ------------------------------------------------------------

    def shotlist(self):
        return list(self._data["shotlist"])

    def in_shotlist(self, sound_id):
        return any(s["id"] == sound_id for s in self._data["shotlist"])

    def add_to_shotlist(self, sound):
        """Returns False if the sound was already in the shotlist."""
        if self.in_shotlist(sound["id"]):
            return False
        self._data["shotlist"].append(sound)
        self._commit()
        return True

    def remove_from_shotlist(self, sound_id):
        self._data["shotlist"] = [
            s for s in self._data["shotlist"] if s["id"] != sound_id]
        self._commit()

    def clear_shotlist(self):
        self._data["shotlist"] = []
        self._commit()

    # -- playlists -----------------------------------------------------------

    def playlists(self):
        return dict(self._data["playlists"])

    def playlist(self, name):
        return list(self._data["playlists"].get(name, []))

    def has_playlist(self, name):
        return name in self._data["playlists"]

    def save_playlist(self, name, sounds):
        self._data["playlists"][name] = list(sounds)
        self._commit()

    def delete_playlist(self, name):
        if self._data["playlists"].pop(name, None) is not None:
            self._commit()

    def rename_playlist(self, old, new):
        """Returns False if `old` doesn't exist or `new` is taken."""
        playlists = self._data["playlists"]
        if old not in playlists or new in playlists:
            return False
        playlists[new] = playlists.pop(old)
        self._commit()
        return True

    def remove_from_playlist(self, name, sound_id):
        sounds = self._data["playlists"].get(name)
        if sounds is None:
            return
        self._data["playlists"][name] = [
            s for s in sounds if s["id"] != sound_id]
        self._commit()

    # -- persistence ---------------------------------------------------------

    def _commit(self):
        try:
            save_playlists(self._data)
        except OSError:
            pass  # keep the in-memory state usable even if the disk write fails
        self.changed.emit()
