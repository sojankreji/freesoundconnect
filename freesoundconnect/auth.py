"""OAuth2 login ("Log in with Freesound") and token management."""

import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from .api import FreesoundError, _http_get, _http_post_form
from .config import (
    API_BASE, AUTHORIZE_URL, CLIENT_ID, CLIENT_SECRET, REDIRECT_PORT,
    REDIRECT_URI, TOKEN_URL, save_config,
)


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
