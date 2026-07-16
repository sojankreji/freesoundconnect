#!/usr/bin/env python3
"""
Freesound Connect — a standalone companion app for DaVinci Resolve
==================================================================

Search freesound.org, preview sounds, and drag them straight onto your
DaVinci Resolve timeline (or Media Pool). Works with BOTH the free
version of Resolve and Studio, because it uses plain OS drag-and-drop
instead of Resolve's Studio-only scripting/UI APIs.

Sign-in uses Freesound's OAuth2 ("Log in with Freesound"), which unlocks
original-quality downloads instead of compressed previews.

Run:  python3 freesound_connect.py   (requires PySide6, see README.md)

License: MIT — https://github.com/sojankreji/freesoundconnect
Freesound API docs: https://freesound.org/docs/api/
"""

import json
import os
import re
import ssl
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from PySide6.QtCore import Qt, QThread, QUrl, Signal, QMimeData
    from PySide6.QtGui import (
        QDrag, QDesktopServices, QIcon, QPainter, QPainterPath, QPixmap,
    )
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtWidgets import (
        QAbstractItemView, QApplication, QComboBox, QDialog, QHBoxLayout,
        QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
        QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
    )
except ImportError:
    sys.exit(
        "Freesound Connect needs PySide6.\n"
        "Install it with:  pip3 install PySide6\n"
        "(or:  pip3 install -r requirements.txt )"
    )

APP_NAME = "Freesound Connect"
VERSION = "2.0.0"


def resource_path(*parts):
    """Resolve bundled files both from source and from a PyInstaller build."""
    base = getattr(sys, "_MEIPASS",
                   os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


try:
    # Real OAuth app credentials, gitignored — see oauth_credentials.example.py
    from oauth_credentials import CLIENT_ID, CLIENT_SECRET
except ImportError:
    CLIENT_ID = os.environ.get("FREESOUND_CLIENT_ID", "")
    CLIENT_SECRET = os.environ.get("FREESOUND_CLIENT_SECRET", "")

API_BASE = "https://freesound.org/apiv2"
AUTHORIZE_URL = "https://freesound.org/apiv2/oauth2/authorize/"
TOKEN_URL = "https://freesound.org/apiv2/oauth2/access_token/"
REDIRECT_PORT = 8918
REDIRECT_URI = "http://127.0.0.1:%d/callback" % REDIRECT_PORT
PAGE_SIZE = 30
SEARCH_FIELDS = "id,name,previews,duration,username,license,url,type"

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".freesoundconnect")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.join(CONFIG_DIR, "error.log")
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
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass


def log_error(context, err):
    """Best-effort debug log — packaged windowed apps have no visible
    console, so unexpected errors would otherwise vanish silently."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("[%s] %s: %s\n" % (
                time.strftime("%Y-%m-%d %H:%M:%S"), context, err))
            if err.__traceback__:
                fh.write(traceback.format_exc())
                fh.write("\n")
    except OSError:
        pass


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


def _http_get(url, access_token=None):
    headers = {"User-Agent": "%s/%s" % (APP_NAME.replace(" ", ""), VERSION)}
    if access_token:
        headers["Authorization"] = "Bearer %s" % access_token
    req = urllib.request.Request(url, headers=headers)
    try:
        return urllib.request.urlopen(req, timeout=30, context=_ssl_context())
    except urllib.error.HTTPError as err:
        if err.code == 401:
            raise FreesoundError("Your Freesound login expired. Please log "
                                 "in again.")
        raise FreesoundError("Freesound returned HTTP %d." % err.code)
    except urllib.error.URLError as err:
        if isinstance(err.reason, ssl.SSLCertVerificationError):
            raise FreesoundError(
                "SSL certificates missing for your Python. Fix: run "
                "'pip3 install certifi', or on macOS run 'Install "
                "Certificates.command' inside your Python folder in "
                "/Applications.")
        raise FreesoundError("Network error: %s" % err.reason)


def _http_post_form(url, data):
    body = urllib.parse.urlencode(data).encode("utf-8")
    headers = {
        "User-Agent": "%s/%s" % (APP_NAME.replace(" ", ""), VERSION),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    req = urllib.request.Request(url, data=body, headers=headers,
                                  method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30,
                                    context=_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "ignore")[:200]
        raise FreesoundError("Freesound login error (HTTP %d): %s"
                             % (err.code, detail))
    except urllib.error.URLError as err:
        raise FreesoundError("Network error: %s" % err.reason)


def search_sounds(access_token, query, page=1, sort="score",
                   license_filter=None):
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
    with _http_get(url, access_token) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(url, dest, access_token=None):
    tmp = dest + ".part"
    with _http_get(url, access_token) as resp, open(tmp, "wb") as out:
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


def original_download_url(sound):
    return "%s/sounds/%s/download/" % (API_BASE, sound["id"])


def sanitize_filename(name):
    name = re.sub(r"[^\w\s.-]", "", name).strip()
    name = re.sub(r"[\s]+", "_", name)
    return name[:80] or "sound"


def original_filename(sound):
    ext = sound.get("type") or "wav"
    return "%s__%s.%s" % (sound["id"], sanitize_filename(sound["name"]), ext)


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
# OAuth2 ("Log in with Freesound")
# ---------------------------------------------------------------------------

def build_authorize_url():
    params = {"client_id": CLIENT_ID, "response_type": "code"}
    return "%s?%s" % (AUTHORIZE_URL, urllib.parse.urlencode(params))


def exchange_code_for_tokens(code):
    return _http_post_form(TOKEN_URL, {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    })


def refresh_access_token(refresh_token_value):
    return _http_post_form(TOKEN_URL, {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token_value,
    })


def fetch_profile(access_token):
    with _http_get("%s/me/" % API_BASE, access_token) as resp:
        me = json.loads(resp.read().decode("utf-8"))
    username = me.get("username")
    avatar_url = None
    if username:
        try:
            user_url = "%s/users/%s/" % (API_BASE, urllib.parse.quote(username))
            with _http_get(user_url) as resp:
                user = json.loads(resp.read().decode("utf-8"))
            avatar = user.get("avatar") or {}
            avatar_url = avatar.get("medium") or avatar.get("small") \
                or avatar.get("large")
        except FreesoundError:
            pass
    return {"username": username, "avatar_url": avatar_url}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self.server.auth_code = params.get("code", [None])[0]
        self.server.auth_error = params.get("error", [None])[0]
        ok = bool(self.server.auth_code)
        message = ("You're logged in to Freesound Connect. You can close "
                  "this tab.") if ok else \
            "Login failed or was cancelled. You can close this tab."
        body = ("<html><body style='font-family:sans-serif;text-align:"
               "center;padding:60px'><h2>%s</h2></body></html>" % message)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, fmt, *args):
        pass  # silence default request logging


def wait_for_oauth_code(timeout=300):
    try:
        server = HTTPServer(("127.0.0.1", REDIRECT_PORT), _CallbackHandler)
    except OSError as err:
        raise FreesoundError(
            "Could not start local login listener on port %d: %s"
            % (REDIRECT_PORT, err))
    server.timeout = timeout
    server.auth_code = None
    server.auth_error = None
    try:
        server.handle_request()
    finally:
        server.server_close()
    if server.auth_code:
        return server.auth_code
    if server.auth_error:
        raise FreesoundError("Freesound login failed: %s" % server.auth_error)
    raise FreesoundError("Login timed out waiting for the browser. Please "
                         "try again.")


class AuthManager:
    """Holds OAuth2 tokens, persists them, and refreshes on demand.

    ensure_valid_token() does blocking network I/O — only call it from a
    background thread, never from the Qt main/UI thread.
    """

    def __init__(self, config):
        self.config = config
        data = config.get("oauth") or {}
        self.access_token = data.get("access_token")
        self.refresh_token_value = data.get("refresh_token")
        self.expires_at = data.get("expires_at", 0)
        self.username = data.get("username")
        self.avatar_url = data.get("avatar_url")
        self._lock = threading.Lock()

    def is_logged_in(self):
        return bool(self.refresh_token_value)

    def _persist(self):
        self.config["oauth"] = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token_value,
            "expires_at": self.expires_at,
            "username": self.username,
            "avatar_url": self.avatar_url,
        }
        save_config(self.config)

    def apply_tokens(self, token_data):
        self.access_token = token_data["access_token"]
        self.refresh_token_value = token_data.get(
            "refresh_token", self.refresh_token_value)
        self.expires_at = time.time() + float(
            token_data.get("expires_in", 3600)) - 60
        self._persist()

    def apply_profile(self, profile):
        self.username = profile.get("username")
        self.avatar_url = profile.get("avatar_url")
        self._persist()

    def ensure_valid_token(self):
        with self._lock:
            if not self.refresh_token_value:
                raise FreesoundError("Not logged in.")
            if self.access_token and time.time() < self.expires_at:
                return self.access_token
            self.apply_tokens(refresh_access_token(self.refresh_token_value))
            return self.access_token

    def logout(self):
        self.access_token = None
        self.refresh_token_value = None
        self.expires_at = 0
        self.username = None
        self.avatar_url = None
        self.config.pop("oauth", None)
        save_config(self.config)


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class RedirectWaiterWorker(QThread):
    """Waits for Freesound's browser redirect to hit our local callback
    server. Runs alongside manual code entry — whichever completes first
    wins (see LoginDialog)."""
    succeeded = Signal(str)  # authorization code
    failed = Signal(str)

    def run(self):
        try:
            self.succeeded.emit(wait_for_oauth_code())
        except FreesoundError as err:
            self.failed.emit(str(err))


class TokenExchangeWorker(QThread):
    succeeded = Signal(dict, dict)  # token_data, profile
    failed = Signal(str)

    def __init__(self, code, parent=None):
        super().__init__(parent)
        self._code = code

    def run(self):
        try:
            token_data = exchange_code_for_tokens(self._code)
            if "access_token" not in token_data:
                raise FreesoundError(
                    "Unexpected response from Freesound: %s" % token_data)
        except Exception as err:  # noqa: BLE001 - must always report, never hang
            log_error("token_exchange", err)
            self.failed.emit("Login failed: %s" % err)
            return
        try:
            profile = fetch_profile(token_data["access_token"])
        except Exception as err:  # noqa: BLE001 - profile is best-effort
            log_error("fetch_profile", err)
            profile = {"username": None, "avatar_url": None}
        self.succeeded.emit(token_data, profile)


class AvatarWorker(QThread):
    succeeded = Signal(bytes)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            with _http_get(self._url) as resp:
                self.succeeded.emit(resp.read())
        except FreesoundError:
            pass


class SearchWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, auth, query, page, sort, license_filter, parent=None):
        super().__init__(parent)
        self._auth = auth
        self._args = (query, page, sort, license_filter)

    def run(self):
        try:
            token = self._auth.ensure_valid_token()
            self.succeeded.emit(search_sounds(token, *self._args))
        except FreesoundError as err:
            self.failed.emit(str(err))


def make_circular_pixmap(pixmap, size):
    scaled = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
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


# ---------------------------------------------------------------------------
# Login dialog
# ---------------------------------------------------------------------------

class LoginDialog(QDialog):
    """Shown while logging in. A background thread waits for Freesound's
    browser redirect to reach our local callback server, but the user can
    also paste the authorization code (or the whole redirect URL) by
    hand — needed when the automatic redirect can't reach localhost, e.g.
    behind a strict firewall/proxy or an unusual browser setup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.code = None
        self.setWindowTitle("Log in with Freesound")
        self.setMinimumWidth(480)

        info = QLabel(
            "A browser window opened for you to log in to Freesound.\n\n"
            "If it doesn't redirect back here automatically within a few "
            "seconds of approving, copy the authorization code (or the "
            "whole address-bar URL) from the browser and paste it below.")
        info.setWordWrap(True)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText(
            "Paste authorization code or redirect URL here")
        self.code_edit.returnPressed.connect(self._submit_manual)

        submit_btn = QPushButton("Submit code")
        submit_btn.setObjectName("PrimaryButton")
        submit_btn.clicked.connect(self._submit_manual)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(submit_btn)

        self.status_label = QLabel("Waiting for the browser…")
        self.status_label.setObjectName("Hint")
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(self.code_edit)
        layout.addLayout(buttons)
        layout.addWidget(self.status_label)

        self._waiter = RedirectWaiterWorker()
        self._waiter.succeeded.connect(self._on_auto_code)
        self._waiter.failed.connect(self._on_wait_failed)
        self._waiter.start()

    def _submit_manual(self):
        text = self.code_edit.text().strip()
        if not text:
            return
        self.code = self._extract_code(text)
        self.accept()

    @staticmethod
    def _extract_code(text):
        if "code=" in text:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(text).query)
            values = params.get("code")
            if values:
                return values[0]
        return text

    def _on_auto_code(self, code):
        self.code = code
        self.accept()

    def _on_wait_failed(self, message):
        self.status_label.setText(
            "%s You can still paste the code manually above." % message)

    def done(self, result):  # noqa: N802 (Qt override)
        # The waiter thread blocks in a system call we cannot interrupt;
        # let it run to its own timeout in the background instead of
        # freezing the dialog close on wait().
        self._waiter.succeeded.disconnect(self._on_auto_code)
        self._waiter.failed.disconnect(self._on_wait_failed)
        super().done(result)


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
# Modern theme
# ---------------------------------------------------------------------------

STYLESHEET = """
QWidget {
    background: #12152b;
    color: #e7e9f5;
    font-size: 13px;
}
QLabel#Hint {
    color: #9aa0c3;
    padding: 4px 2px;
}
QLabel#Status {
    color: #9aa0c3;
    padding-top: 4px;
}
QLabel#AppTitle {
    font-size: 17px;
    font-weight: 600;
    color: #ffffff;
}
QLineEdit, QComboBox {
    background: #1b2044;
    border: 1px solid #2a3060;
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: #35e0c3;
    selection-color: #0c0f1f;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #4f9dff;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background: #1b2044;
    border: 1px solid #2a3060;
    selection-background-color: #2a3161;
    outline: none;
}
QPushButton {
    background: #1e2450;
    border: 1px solid #2a3060;
    border-radius: 8px;
    padding: 7px 14px;
    color: #e7e9f5;
}
QPushButton:hover {
    background: #262d5c;
    border: 1px solid #3a4280;
}
QPushButton:pressed {
    background: #171b3d;
}
QPushButton:disabled {
    color: #5c6289;
}
QPushButton#PrimaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                 stop:0 #35e0c3, stop:1 #4f9dff);
    color: #0c0f1f;
    font-weight: 600;
    border: none;
}
QPushButton#PrimaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                 stop:0 #4aeed3, stop:1 #66aeff);
}
QPushButton#PrimaryButton:disabled {
    background: #2a3060;
    color: #5c6289;
}
QPushButton#LogoutButton {
    background: transparent;
    border: none;
    color: #9aa0c3;
    padding: 4px 8px;
}
QPushButton#LogoutButton:hover {
    color: #ff8fa3;
}
QLabel#Username {
    color: #e7e9f5;
    font-weight: 500;
}
QTreeWidget {
    background: #171b3d;
    alternate-background-color: #1a1f45;
    border: 1px solid #262c56;
    border-radius: 10px;
    padding: 2px;
}
QTreeWidget::item {
    padding: 6px 4px;
    border: none;
}
QTreeWidget::item:selected {
    background: #2a4a6b;
    color: #ffffff;
    border-radius: 4px;
}
QHeaderView::section {
    background: #12152b;
    color: #9aa0c3;
    border: none;
    border-bottom: 1px solid #262c56;
    padding: 6px 4px;
    font-weight: 600;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #2a3060;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.auth = AuthManager(self.config)
        self.results = []
        self.page = 1
        self.total_pages = 1
        self.last_query = ""
        self.local_files = {}  # sound id -> downloaded original file path
        self.workers = []
        self._pending_search = False

        self.audio_out = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_out)
        self.player.errorOccurred.connect(self._on_player_error)

        self._build_ui()
        self._refresh_account_ui()

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        self.setWindowTitle("%s %s" % (APP_NAME, VERSION))
        self.setStyleSheet(STYLESHEET)
        self.resize(960, 620)

        # Header: logo, title, account area (login button / avatar + name)
        logo = QLabel()
        icon_path = resource_path("assets", "icon.png")
        if os.path.isfile(icon_path):
            logo.setPixmap(QPixmap(icon_path).scaled(
                32, 32, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        title = QLabel(APP_NAME)
        title.setObjectName("AppTitle")

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

        header = QHBoxLayout()
        header.addWidget(logo)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.account_stack)

        # Search row
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
        search_btn.setObjectName("PrimaryButton")
        search_btn.clicked.connect(self.on_search)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self.query_edit, 1)
        top.addWidget(self.license_combo)
        top.addWidget(self.sort_combo)
        top.addWidget(search_btn)

        hint = QLabel(
            "🎵  Drag a sound from the list below onto your DaVinci Resolve "
            "timeline (or Media Pool). Double-click to preview.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)

        self.tree = ResultsTree(self.ensure_local_file)
        self.tree.itemDoubleClicked.connect(lambda *_: self.on_preview())

        self.prev_btn = QPushButton("‹ Prev")
        self.prev_btn.clicked.connect(lambda: self.change_page(-1))
        self.next_btn = QPushButton("Next ›")
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

        nav = QHBoxLayout()
        nav.setSpacing(8)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.page_label)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        nav.addWidget(preview_btn)
        nav.addWidget(stop_btn)
        nav.addWidget(open_btn)
        nav.addWidget(folder_btn)

        self.status = QLabel("Ready.")
        self.status.setObjectName("Status")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addLayout(top)
        layout.addWidget(hint)
        layout.addWidget(self.tree, 1)
        layout.addLayout(nav)
        layout.addWidget(self.status)

    def set_status(self, text):
        self.status.setText(text)

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
            self.on_search()

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
        self.page = 1
        self.run_search()

    def change_page(self, delta):
        new_page = self.page + delta
        if not self.last_query or new_page < 1 or new_page > self.total_pages:
            return
        self.page = new_page
        self.run_search(query=self.last_query)

    def run_search(self, query=None):
        if not self.auth.is_logged_in():
            self._pending_search = True
            self.on_login_clicked()
            return

        query = query if query is not None else self.query_edit.text().strip()
        if not query:
            self.set_status("Type something to search for.")
            return

        license_filter = LICENSE_CHOICES[self.license_combo.currentIndex()][1]
        sort = SORT_CHOICES[self.sort_combo.currentIndex()][1]

        self.set_status("Searching for “%s”…" % query)
        worker = SearchWorker(self.auth, query, self.page, sort, license_filter)
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
        return os.path.join(self.download_dir(), original_filename(sound))

    def ensure_local_file(self, sound):
        """Called at drag start — must return a real file path. Downloads
        the original-quality file (needs a valid OAuth2 login) and blocks
        briefly with a wait cursor if it isn't cached yet."""
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
    icon_path = resource_path("assets", "icon.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.show()
    if not win.auth.is_logged_in():
        win.set_status(
            "Click “Log in with Freesound” to search and add sounds.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
