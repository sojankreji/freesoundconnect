#!/usr/bin/env python3
"""
Freesound Connect — a standalone companion app for DaVinci Resolve
==================================================================

Search freesound.org, preview sounds, and drag them straight onto your
DaVinci Resolve timeline (or Media Pool). Works with BOTH the free
version of Resolve and Studio, because it uses plain OS drag-and-drop
instead of Resolve's Studio-only scripting/UI APIs.

Run:  python3 freesound_connect.py   (requires PySide6, see README.md)

License: MIT — https://github.com/YOUR_USERNAME/freesound-connect
Freesound API docs: https://freesound.org/docs/api/
"""

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    from PySide6.QtCore import Qt, QThread, QUrl, Signal, QMimeData
    from PySide6.QtGui import QDrag, QDesktopServices
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtWidgets import (
        QAbstractItemView, QApplication, QComboBox, QDialog, QHBoxLayout,
        QHeaderView, QLabel, QLineEdit, QPushButton, QTreeWidget,
        QTreeWidgetItem, QVBoxLayout, QWidget,
    )
except ImportError:
    sys.exit(
        "Freesound Connect needs PySide6.\n"
        "Install it with:  pip3 install PySide6\n"
        "(or:  pip3 install -r requirements.txt )"
    )

APP_NAME = "Freesound Connect"
VERSION = "0.2.0"

API_BASE = "https://freesound.org/apiv2"
APPLY_URL = "https://freesound.org/apiv2/apply/"
PAGE_SIZE = 30
SEARCH_FIELDS = "id,name,previews,duration,username,license,url"

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".freesound-connect")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_DOWNLOAD_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "FreesoundConnect"
)

LICENSE_CHOICES = [
    ("Any license", None),
    ("CC0 (public domain)", '"Creative Commons 0"'),
    ("CC-BY (attribution)", '"Attribution"'),
    ("CC-BY-NC (non-commercial)", '"Attribution Noncommercial"'),
]

SORT_CHOICES = [
    ("Relevance", "score"),
    ("Most downloaded", "downloads_desc"),
    ("Highest rated", "rating_desc"),
    ("Newest", "created_desc"),
    ("Shortest", "duration_asc"),
    ("Longest", "duration_desc"),
]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)


# ---------------------------------------------------------------------------
# Freesound API
# ---------------------------------------------------------------------------

class FreesoundError(Exception):
    pass


def _ssl_context():
    """System certificate store first; fall back to certifi if the system
    store is missing roots (common with python.org installs on macOS)."""
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca", 0) == 0:
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass
    return ctx


def _http_get(url, token=None):
    headers = {"User-Agent": "%s/%s" % (APP_NAME.replace(" ", ""), VERSION)}
    if token:
        headers["Authorization"] = "Token %s" % token
    req = urllib.request.Request(url, headers=headers)
    try:
        return urllib.request.urlopen(req, timeout=30, context=_ssl_context())
    except urllib.error.HTTPError as err:
        if err.code == 401:
            raise FreesoundError("Invalid API key (401). Check Settings.")
        raise FreesoundError("Freesound returned HTTP %d." % err.code)
    except urllib.error.URLError as err:
        if isinstance(err.reason, ssl.SSLCertVerificationError):
            raise FreesoundError(
                "SSL certificates missing for your Python. Fix: run "
                "'pip3 install certifi', or on macOS run 'Install "
                "Certificates.command' inside your Python folder in "
                "/Applications.")
        raise FreesoundError("Network error: %s" % err.reason)


def search_sounds(token, query, page=1, sort="score", license_filter=None):
    params = {
        "query": query,
        "page": page,
        "page_size": PAGE_SIZE,
        "fields": SEARCH_FIELDS,
        "sort": sort,
    }
    if license_filter:
        params["filter"] = "license:%s" % license_filter
    url = "%s/search/text/?%s" % (API_BASE, urllib.parse.urlencode(params))
    with _http_get(url, token) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(url, dest, token=None):
    tmp = dest + ".part"
    with _http_get(url, token) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            out.write(chunk)
    os.replace(tmp, dest)
    return dest


def preview_url(sound):
    previews = sound.get("previews", {})
    url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
    if not url:
        raise FreesoundError("No preview available for this sound.")
    return url


def sanitize_filename(name):
    name = re.sub(r"[^\w\s.-]", "", name).strip()
    name = re.sub(r"[\s]+", "_", name)
    return name[:80] or "sound"


def sound_filename(sound):
    return "%s__%s.mp3" % (sound["id"], sanitize_filename(sound["name"]))


def format_duration(seconds):
    seconds = float(seconds)
    mins = int(seconds // 60)
    return "%d:%05.2f" % (mins, seconds - mins * 60)


def short_license(url):
    return (url or "").replace(
        "http://creativecommons.org/licenses/", "CC ").replace(
        "https://creativecommons.org/licenses/", "CC ").replace(
        "http://creativecommons.org/publicdomain/zero/1.0/", "CC0").replace(
        "https://creativecommons.org/publicdomain/zero/1.0/", "CC0")


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class SearchWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, token, query, page, sort, license_filter, parent=None):
        super().__init__(parent)
        self._args = (token, query, page, sort, license_filter)

    def run(self):
        try:
            self.succeeded.emit(search_sounds(*self._args))
        except FreesoundError as err:
            self.failed.emit(str(err))


class DownloadWorker(QThread):
    succeeded = Signal(int, str)  # sound id, local path
    failed = Signal(int, str)

    def __init__(self, sound, dest, token, parent=None):
        super().__init__(parent)
        self._sound = sound
        self._dest = dest
        self._token = token

    def run(self):
        try:
            download_file(preview_url(self._sound), self._dest, self._token)
            self.succeeded.emit(self._sound["id"], self._dest)
        except (FreesoundError, OSError) as err:
            self.failed.emit(self._sound["id"], str(err))


# ---------------------------------------------------------------------------
# Draggable results list
# ---------------------------------------------------------------------------

class ResultsTree(QTreeWidget):
    """Result rows can be dragged out of the app as real audio files —
    drop them on Resolve's timeline or Media Pool (or any other app)."""

    def __init__(self, ensure_local_file, parent=None):
        super().__init__(parent)
        self._ensure_local_file = ensure_local_file
        self.setDragEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(True)
        self.setHeaderLabels(["Name", "Duration", "Author", "License"])
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

    def startDrag(self, supported_actions):  # noqa: N802 (Qt override)
        item = self.currentItem()
        if not item:
            return
        sound = item.data(0, Qt.ItemDataRole.UserRole)
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


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------

class ApiKeyDialog(QDialog):
    def __init__(self, current_key, parent=None):
        super().__init__(parent)
        self.setWindowTitle("%s — API Key" % APP_NAME)
        self.setMinimumWidth(520)

        intro = QLabel(
            "Freesound Connect needs a free Freesound API key.<br><br>"
            "1. Create an account at "
            "<a href='https://freesound.org'>freesound.org</a><br>"
            "2. Request a key at <a href='%s'>%s</a><br>"
            "&nbsp;&nbsp;&nbsp;(any name/description is fine, leave the "
            "OAuth fields empty)<br>"
            "3. Paste the key below." % (APPLY_URL, APPLY_URL)
        )
        intro.setOpenExternalLinks(True)
        intro.setWordWrap(True)

        self.key_edit = QLineEdit(current_key or "")
        self.key_edit.setPlaceholderText("Paste your Freesound API key here")

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.key_edit)
        layout.addLayout(buttons)

    def api_key(self):
        return self.key_edit.text().strip()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.results = []
        self.page = 1
        self.total_pages = 1
        self.last_query = ""
        self.local_files = {}      # sound id -> downloaded path
        self.pending_downloads = set()
        self.workers = []

        self.audio_out = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_out)
        self.player.errorOccurred.connect(self._on_player_error)

        self._build_ui()

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        self.setWindowTitle("%s %s" % (APP_NAME, VERSION))
        self.resize(920, 600)

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText(
            "Search freesound.org  (e.g. rain, whoosh, door slam)")
        self.query_edit.returnPressed.connect(self.on_search)

        self.license_combo = QComboBox()
        for label, _ in LICENSE_CHOICES:
            self.license_combo.addItem(label)
        self.sort_combo = QComboBox()
        for label, _ in SORT_CHOICES:
            self.sort_combo.addItem(label)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.on_search)

        top = QHBoxLayout()
        top.addWidget(self.query_edit, 1)
        top.addWidget(self.license_combo)
        top.addWidget(self.sort_combo)
        top.addWidget(search_btn)

        hint = QLabel(
            "🎵  <b>Drag a sound from the list below onto your DaVinci "
            "Resolve timeline</b> (or Media Pool). Double-click to preview.")
        hint.setWordWrap(True)

        self.tree = ResultsTree(self.ensure_local_file)
        self.tree.itemDoubleClicked.connect(lambda *_: self.on_preview())
        self.tree.currentItemChanged.connect(self._on_selection_changed)

        self.prev_btn = QPushButton("< Prev")
        self.prev_btn.clicked.connect(lambda: self.change_page(-1))
        self.next_btn = QPushButton("Next >")
        self.next_btn.clicked.connect(lambda: self.change_page(+1))
        self.page_label = QLabel("")

        preview_btn = QPushButton("▶ Preview")
        preview_btn.clicked.connect(self.on_preview)
        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self.player.stop)
        open_btn = QPushButton("Open on Freesound")
        open_btn.clicked.connect(self.on_open_in_browser)
        folder_btn = QPushButton("Downloads Folder")
        folder_btn.clicked.connect(self.on_open_downloads)
        settings_btn = QPushButton("API Key…")
        settings_btn.clicked.connect(self.show_settings)

        nav = QHBoxLayout()
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.page_label)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        nav.addWidget(preview_btn)
        nav.addWidget(stop_btn)
        nav.addWidget(open_btn)
        nav.addWidget(folder_btn)
        nav.addWidget(settings_btn)

        self.status = QLabel("Ready.")

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(hint)
        layout.addWidget(self.tree, 1)
        layout.addLayout(nav)
        layout.addWidget(self.status)

    def set_status(self, text):
        self.status.setText(text)

    # -- Settings -----------------------------------------------------------

    def show_settings(self):
        dlg = ApiKeyDialog(self.config.get("api_key", ""), self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.api_key():
            self.config["api_key"] = dlg.api_key()
            save_config(self.config)
            self.set_status("API key saved.")

    def require_api_key(self):
        if not self.config.get("api_key"):
            self.show_settings()
        return self.config.get("api_key")

    # -- Search -------------------------------------------------------------

    def on_search(self):
        self.page = 1
        self.run_search()

    def change_page(self, delta):
        new_page = self.page + delta
        if not self.last_query or new_page < 1 or new_page > self.total_pages:
            return
        self.page = new_page
        self.run_search(query=self.last_query)

    def run_search(self, query=None):
        token = self.require_api_key()
        if not token:
            return
        query = query if query is not None else self.query_edit.text().strip()
        if not query:
            self.set_status("Type something to search for.")
            return

        license_filter = LICENSE_CHOICES[self.license_combo.currentIndex()][1]
        sort = SORT_CHOICES[self.sort_combo.currentIndex()][1]

        self.set_status("Searching for “%s”…" % query)
        worker = SearchWorker(token, query, self.page, sort, license_filter)
        worker.succeeded.connect(
            lambda data, q=query: self._on_search_done(q, data))
        worker.failed.connect(self.set_status)
        self._track_worker(worker)
        worker.start()

    def _on_search_done(self, query, data):
        self.last_query = query
        count = data.get("count", 0)
        self.total_pages = max(1, -(-count // PAGE_SIZE))  # ceil
        self.results = data.get("results", [])

        self.tree.clear()
        for sound in self.results:
            item = QTreeWidgetItem([
                sound.get("name", ""),
                format_duration(sound.get("duration", 0)),
                sound.get("username", ""),
                short_license(sound.get("license", "")),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, sound)
            self.tree.addTopLevelItem(item)

        self.page_label.setText("Page %d / %d" % (self.page, self.total_pages))
        self.set_status("%d sounds found." % count)

    # -- Selection / preview ------------------------------------------------

    def selected_sound(self):
        item = self.tree.currentItem()
        if not item:
            self.set_status("Select a sound first.")
            return None
        return item.data(0, Qt.ItemDataRole.UserRole)

    def _on_selection_changed(self, current, _previous):
        # Prefetch in the background so dragging is instant.
        if current:
            sound = current.data(0, Qt.ItemDataRole.UserRole)
            if sound:
                self.prefetch(sound)

    def on_preview(self):
        sound = self.selected_sound()
        if not sound:
            return
        local = self.local_files.get(sound["id"])
        try:
            url = QUrl.fromLocalFile(local) if local else QUrl(preview_url(sound))
        except FreesoundError as err:
            self.set_status(str(err))
            return
        self.player.stop()
        self.player.setSource(url)
        self.player.play()
        self.set_status("Playing: %s" % sound["name"])

    def _on_player_error(self, _error, message):
        if message:
            self.set_status("Playback error: %s" % message)

    def on_open_in_browser(self):
        sound = self.selected_sound()
        if sound and sound.get("url"):
            QDesktopServices.openUrl(QUrl(sound["url"]))

    def on_open_downloads(self):
        os.makedirs(self.download_dir(), exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.download_dir()))

    # -- Downloads ----------------------------------------------------------

    def download_dir(self):
        return self.config.get("download_dir", DEFAULT_DOWNLOAD_DIR)

    def local_path_for(self, sound):
        return os.path.join(self.download_dir(), sound_filename(sound))

    def prefetch(self, sound):
        sid = sound["id"]
        if sid in self.local_files or sid in self.pending_downloads:
            return
        path = self.local_path_for(sound)
        if os.path.isfile(path):
            self.local_files[sid] = path
            return
        os.makedirs(self.download_dir(), exist_ok=True)
        self.pending_downloads.add(sid)
        worker = DownloadWorker(sound, path, self.config.get("api_key"))
        worker.succeeded.connect(self._on_download_done)
        worker.failed.connect(self._on_download_failed)
        self._track_worker(worker)
        worker.start()

    def _on_download_done(self, sid, path):
        self.pending_downloads.discard(sid)
        self.local_files[sid] = path

    def _on_download_failed(self, sid, message):
        self.pending_downloads.discard(sid)
        self.set_status(message)

    def ensure_local_file(self, sound):
        """Called at drag start — must return a real file path. Blocks
        briefly (with a wait cursor) if the prefetch hasn't finished."""
        sid = sound["id"]
        path = self.local_files.get(sid)
        if not path:
            path = self.local_path_for(sound)
            if not os.path.isfile(path):
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                self.set_status("Downloading “%s”…" % sound["name"])
                try:
                    os.makedirs(self.download_dir(), exist_ok=True)
                    download_file(preview_url(sound), path,
                                  self.config.get("api_key"))
                except (FreesoundError, OSError) as err:
                    self.set_status(str(err))
                    return None
                finally:
                    QApplication.restoreOverrideCursor()
            self.local_files[sid] = path
        self.append_credit(sound)
        self.set_status("Drop “%s” on your Resolve timeline. Credit written "
                        "to CREDITS.txt." % sound["name"])
        return path

    def append_credit(self, sound):
        """Keep an attribution list next to the downloads — most Freesound
        sounds are Creative Commons and CC-BY requires credit."""
        credits_path = os.path.join(self.download_dir(), "CREDITS.txt")
        line = "\"%s\" by %s — %s — License: %s\n" % (
            sound.get("name"), sound.get("username"),
            sound.get("url", "https://freesound.org/s/%s/" % sound["id"]),
            sound.get("license"))
        try:
            existing = ""
            if os.path.isfile(credits_path):
                with open(credits_path, "r", encoding="utf-8") as fh:
                    existing = fh.read()
            if line not in existing:
                with open(credits_path, "a", encoding="utf-8") as fh:
                    fh.write(line)
        except OSError:
            pass  # attribution file is best-effort

    # -- Housekeeping ---------------------------------------------------------

    def _track_worker(self, worker):
        self.workers.append(worker)
        worker.finished.connect(lambda w=worker: self._untrack_worker(w))

    def _untrack_worker(self, worker):
        if worker in self.workers:
            self.workers.remove(worker)
        worker.deleteLater()

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self.player.stop()
        for worker in self.workers:
            worker.wait(2000)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = MainWindow()
    win.show()
    if not win.config.get("api_key"):
        win.show_settings()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
