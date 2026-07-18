"""Main application window: nav rail on the left, pages on the right."""

import os
import webbrowser

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from . import APP_NAME, VERSION, resource_path
from .api import (
    FreesoundError, download_file, format_duration, original_download_url,
    original_filename, sanitize_filename,
)
from .audio import decode_file, write_wav_region
from .auth import AuthManager, build_authorize_url
from .config import (
    CLIENT_ID, CLIENT_SECRET, DEFAULT_DOWNLOAD_DIR, LICENSE_CHOICES,
    PAGE_SIZE, SORT_CHOICES, load_config, log_error,
)
from .login_dialog import LoginDialog
from .nav_sidebar import NavSidebar
from .player_bar import PlayerBar
from .playlists_page import PlaylistsPage
from .search_page import SearchPage
from .shotlist_popup import ShotlistPopup
from .store import PlaylistStore
from .theme import STYLESHEET
from .workers import AvatarWorker, SearchWorker, TokenExchangeWorker

TRENDING_FILTER = "created:[NOW-90DAYS TO NOW]"
TRENDING_LABEL = "🔥 Trending on Freesound — most downloaded of the last 3 months."

PAGE_SEARCH = 0
PAGE_PLAYLISTS = 1


def make_circular_pixmap(pixmap, size):
    scaled = pixmap.scaled(size, size,
                           Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()
    return result


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.auth = AuthManager(self.config)
        self.store = PlaylistStore()
        self.results = []
        self.page = 1
        self.total_pages = 1
        self.local_files = {}  # sound id -> downloaded original file path
        self.workers = []
        self._search_ctx = None    # dict describing the active search
        self._pending_search = False
        self._decoded_original = None  # (sound id, DecodedAudio) cache

        self._build_ui()
        self._refresh_account_ui()
        if self.auth.is_logged_in():
            self.load_trending()

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        self.setWindowTitle("%s %s" % (APP_NAME, VERSION))
        self.setStyleSheet(STYLESHEET)
        self.resize(1220, 780)

        # Left: navigation rail
        self.nav = NavSidebar()
        self.nav.page_selected.connect(self._on_page_selected)

        # Header: shotlist cart + account area
        self.cart_btn = QPushButton()
        self.cart_btn.setObjectName("CartButton")
        self.cart_btn.setToolTip("Review the shotlist — your collected "
                                 "sounds, like a cart")
        self.cart_btn.clicked.connect(self.on_cart_clicked)

        self.login_btn = QPushButton("Log in with Freesound")
        self.login_btn.setObjectName("PrimaryButton")
        self.login_btn.clicked.connect(self.on_login_clicked)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(28, 28)
        self.username_label = QLabel()
        self.username_label.setObjectName("Username")
        self.logout_btn = QPushButton("Log out")
        self.logout_btn.setObjectName("LogoutButton")
        self.logout_btn.clicked.connect(self.on_logout_clicked)

        account_row = QHBoxLayout()
        account_row.setSpacing(8)
        account_row.addWidget(self.avatar_label)
        account_row.addWidget(self.username_label)
        account_row.addWidget(self.logout_btn)
        account_widget = QWidget()
        account_widget.setLayout(account_row)

        self.account_stack = QStackedWidget()
        self.account_stack.addWidget(self.login_btn)   # index 0: logged out
        self.account_stack.addWidget(account_widget)    # index 1: logged in

        self.page_title = QLabel("Search")
        self.page_title.setObjectName("AppTitle")

        header = QHBoxLayout()
        header.addWidget(self.page_title)
        header.addStretch(1)
        header.addWidget(self.cart_btn)
        header.addWidget(self.account_stack)

        # Pages
        self.search_page = SearchPage(self.ensure_local_file)
        self.search_page.query_edit.returnPressed.connect(self.on_search)
        self.search_page.search_btn.clicked.connect(self.on_search)
        self.search_page.prev_btn.clicked.connect(lambda: self.change_page(-1))
        self.search_page.next_btn.clicked.connect(lambda: self.change_page(+1))
        self.search_page.shotlist_btn.clicked.connect(self.on_add_to_shotlist)
        self.search_page.open_btn.clicked.connect(self.on_open_in_browser)
        self.search_page.folder_btn.clicked.connect(self.on_open_downloads)
        self.search_page.tree.currentItemChanged.connect(
            self._on_result_selected)
        self.search_page.tree.itemDoubleClicked.connect(
            lambda *_: self.on_preview())
        # Aliases used throughout the search/pagination logic below.
        self.tree = self.search_page.tree
        self.query_edit = self.search_page.query_edit
        self.license_combo = self.search_page.license_combo
        self.sort_combo = self.search_page.sort_combo
        self.page_label = self.search_page.page_label

        self.playlists_page = PlaylistsPage(self.store, self.ensure_local_file)
        self.playlists_page.status_message.connect(self.set_status)
        self.playlists_page.sound_selected.connect(self._show_in_player)
        self.playlists_page.sound_activated.connect(self._play_sound)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.search_page)      # PAGE_SEARCH
        self.pages.addWidget(self.playlists_page)   # PAGE_PLAYLISTS

        # Shotlist popup (created hidden, toggled from the cart button)
        self.shotlist_popup = ShotlistPopup(self.store, self.ensure_local_file,
                                            self)
        self.shotlist_popup.status_message.connect(self.set_status)
        self.shotlist_popup.sound_selected.connect(self._show_in_player)
        self.shotlist_popup.sound_activated.connect(self._play_sound)

        # Player bar — global, below whichever page is active
        self.player_bar = PlayerBar()
        self.player_bar.status_message.connect(self.set_status)
        self.player_bar.worker_started.connect(self._track_worker)

        self.status = QLabel("Ready.")
        self.status.setObjectName("Status")

        content = QVBoxLayout()
        content.setContentsMargins(16, 14, 16, 14)
        content.setSpacing(10)
        content.addLayout(header)
        content.addWidget(self.pages, 1)
        content.addWidget(self.player_bar)
        content.addWidget(self.status)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.nav)
        outer.addLayout(content, 1)

        self.store.changed.connect(self._refresh_cart_button)
        self._refresh_cart_button()

    def set_status(self, text):
        self.status.setText(text)

    def _on_page_selected(self, index):
        self.pages.setCurrentIndex(index)
        self.page_title.setText("Playlists" if index == PAGE_PLAYLISTS
                                else "Search")

    def _refresh_cart_button(self):
        self.cart_btn.setText("🛒 Shotlist (%d)" % len(self.store.shotlist()))

    def on_cart_clicked(self):
        self.shotlist_popup.toggle_below(self.cart_btn)

    # -- Account / login ------------------------------------------------------

    def _refresh_account_ui(self):
        if self.auth.is_logged_in():
            self.username_label.setText(self.auth.username or "Logged in")
            self.avatar_label.clear()
            if self.auth.avatar_url:
                worker = AvatarWorker(self.auth.avatar_url)
                worker.succeeded.connect(self._on_avatar_loaded)
                self._track_worker(worker)
                worker.start()
            self.account_stack.setCurrentIndex(1)
        else:
            self.account_stack.setCurrentIndex(0)

    def _on_avatar_loaded(self, data):
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.avatar_label.setPixmap(make_circular_pixmap(pixmap, 28))

    def on_login_clicked(self):
        if not CLIENT_ID or not CLIENT_SECRET:
            QMessageBox.warning(
                self, APP_NAME,
                "This build is missing Freesound OAuth credentials.\n\n"
                "See README.md ▸ 'Setting up OAuth credentials (for "
                "maintainers)' for how to register a Freesound app and "
                "supply oauth_credentials.py.")
            return

        self.login_btn.setEnabled(False)
        self.set_status("Opening your browser to log in to Freesound…")
        webbrowser.open(build_authorize_url())

        dialog = LoginDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.code:
            self.login_btn.setEnabled(True)
            self._pending_search = False
            self.set_status("Login cancelled.")
            return

        self.set_status("Finishing login…")
        worker = TokenExchangeWorker(dialog.code)
        worker.succeeded.connect(self._on_login_succeeded)
        worker.failed.connect(self._on_login_failed)
        self._track_worker(worker)
        worker.start()

    def _on_login_succeeded(self, token_data, profile):
        self.auth.apply_tokens(token_data)
        self.auth.apply_profile(profile)
        self.login_btn.setEnabled(True)
        self._refresh_account_ui()
        self.set_status("Logged in as %s." % (self.auth.username or "you"))
        if self._pending_search:
            self._pending_search = False
            self._start_search()
        else:
            self.load_trending()

    def _on_login_failed(self, message):
        self.login_btn.setEnabled(True)
        self._pending_search = False
        self.set_status(message)

    def on_logout_clicked(self):
        self.auth.logout()
        self._refresh_account_ui()
        self.set_status("Logged out.")

    # -- Search -------------------------------------------------------------

    def on_search(self):
        query = self.query_edit.text().strip()
        if not query:
            self.set_status("Type something to search for.")
            return
        self.nav.select_page(PAGE_SEARCH)
        self.page = 1
        self._search_ctx = {"query": query}
        self._start_search()

    def load_trending(self):
        """Fill the results list with recent popular sounds — shown on app
        start and after login, before the user searches for anything."""
        self.page = 1
        self._search_ctx = {
            "query": "",
            "sort": "downloads_desc",
            "extra_filter": TRENDING_FILTER,
            "label": TRENDING_LABEL,
        }
        self._start_search()

    def change_page(self, delta):
        new_page = self.page + delta
        if (self._search_ctx is None or new_page < 1
                or new_page > self.total_pages):
            return
        self.page = new_page
        self._start_search()

    def _start_search(self):
        if not self.auth.is_logged_in():
            self._pending_search = True
            self.on_login_clicked()
            return
        ctx = self._search_ctx
        if ctx is None:
            return

        license_filter = LICENSE_CHOICES[self.license_combo.currentIndex()][1]
        sort = ctx.get("sort") or SORT_CHOICES[self.sort_combo.currentIndex()][1]

        if ctx.get("label"):
            self.set_status("Loading trending sounds…")
        else:
            self.set_status("Searching for “%s”…" % ctx["query"])
        worker = SearchWorker(self.auth, ctx["query"], self.page, sort,
                              license_filter, ctx.get("extra_filter"))
        worker.succeeded.connect(
            lambda data, c=ctx: self._on_search_done(c, data))
        worker.failed.connect(self.set_status)
        self._track_worker(worker)
        worker.start()

    def _on_search_done(self, ctx, data):
        if ctx is not self._search_ctx:
            return  # a newer search superseded this one
        count = data.get("count", 0)
        self.total_pages = max(1, -(-count // PAGE_SIZE))  # ceil
        self.results = data.get("results", [])
        self.tree.set_sounds(self.results)
        self.page_label.setText("Page %d / %d" % (self.page, self.total_pages))
        self.set_status(ctx.get("label") or "%d sounds found." % count)

    # -- Selection / preview ------------------------------------------------

    def selected_sound(self):
        sound = self.tree.current_sound()
        if not sound:
            self.set_status("Select a sound first.")
            return None
        return sound

    def _on_result_selected(self, *_args):
        sound = self.tree.current_sound()
        if sound:
            self.player_bar.load_sound(sound)

    def _show_in_player(self, sound):
        self.player_bar.load_sound(sound)

    def _play_sound(self, sound):
        self.player_bar.play_sound(sound)

    def on_preview(self):
        sound = self.selected_sound()
        if sound:
            self.player_bar.play_sound(sound)

    def on_add_to_shotlist(self):
        sound = self.selected_sound()
        if not sound:
            return
        if self.store.add_to_shotlist(sound):
            self.set_status("Added “%s” to the shotlist." % sound.get("name"))
        else:
            self.set_status("“%s” is already in the shotlist." %
                            sound.get("name"))

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
        return os.path.join(self.download_dir(), original_filename(sound))

    def ensure_local_file(self, sound):
        """Called at drag start — must return a real file path. Downloads
        the original-quality file (needs a valid OAuth2 login) and blocks
        briefly with a wait cursor if it isn't cached yet. If a waveform
        region is selected for this sound, exports and returns just that
        region as a WAV instead."""
        if not self.auth.is_logged_in():
            self.set_status("Log in with Freesound first.")
            return None

        sid = sound["id"]
        path = self.local_files.get(sid)
        if not path:
            path = self.local_path_for(sound)
            if not os.path.isfile(path):
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                self.set_status(
                    "Downloading original-quality “%s”…" % sound["name"])
                try:
                    token = self.auth.ensure_valid_token()
                    os.makedirs(self.download_dir(), exist_ok=True)
                    download_file(original_download_url(sound), path, token)
                except (FreesoundError, OSError) as err:
                    self.set_status(str(err))
                    return None
                finally:
                    QApplication.restoreOverrideCursor()
            self.local_files[sid] = path

        selection = None
        if self.player_bar.sound and self.player_bar.sound["id"] == sid:
            selection = self.player_bar.selection_seconds()
        if selection:
            region = self._export_region(sound, path, selection)
            if region:
                path = region

        self.append_credit(sound)
        self.set_status("Drop “%s” on your Resolve timeline. Credit written "
                        "to CREDITS.txt." % sound["name"])
        return path

    def _export_region(self, sound, original_path, selection):
        """Cut [start, end] out of the sound and return the trimmed WAV."""
        start_s, end_s = selection
        dest = os.path.join(self.download_dir(), "%s__%s__%dms-%dms.wav" % (
            sound["id"], sanitize_filename(sound["name"]),
            int(start_s * 1000), int(end_s * 1000)))
        if os.path.isfile(dest):
            return dest

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.set_status("Exporting %s–%s of “%s”…" % (
            format_duration(start_s), format_duration(end_s), sound["name"]))
        try:
            decoded = None
            if self._decoded_original and \
                    self._decoded_original[0] == sound["id"]:
                decoded = self._decoded_original[1]
            if decoded is None:
                try:
                    decoded = decode_file(original_path)
                    self._decoded_original = (sound["id"], decoded)
                except FreesoundError as err:
                    log_error("decode_original", err)
                    # Fall back to the already-decoded preview quality.
                    decoded = self.player_bar.preview_audio
            if decoded is None:
                self.set_status("Could not decode “%s” — inserting the "
                                "whole file instead." % sound["name"])
                return None
            os.makedirs(self.download_dir(), exist_ok=True)
            return write_wav_region(decoded, start_s, end_s, dest)
        except (FreesoundError, OSError) as err:
            self.set_status(str(err))
            return None
        finally:
            QApplication.restoreOverrideCursor()

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
        self.shotlist_popup.close()
        self.player_bar.stop()
        for worker in self.workers:
            worker.wait(2000)
        super().closeEvent(event)


def run():
    import sys

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon_path = resource_path("assets", "icon.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.show()
    if not win.auth.is_logged_in():
        win.set_status(
            "Click “Log in with Freesound” to search and add sounds.")
    sys.exit(app.exec())
