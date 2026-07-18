"""Background QThread workers."""

import os

from PySide6.QtCore import QThread, Signal

from .api import FreesoundError, _http_get, download_file, preview_url, search_sounds
from .audio import compute_peaks, decode_file
from .auth import exchange_code_for_tokens, fetch_profile, wait_for_oauth_code
from .config import PREVIEW_CACHE_DIR, log_error


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

    def __init__(self, auth, query, page, sort, license_filter,
                 extra_filter=None, parent=None):
        super().__init__(parent)
        self._auth = auth
        self._args = (query, page, sort, license_filter, extra_filter)

    def run(self):
        try:
            token = self._auth.ensure_valid_token()
            self.succeeded.emit(search_sounds(token, *self._args))
        except FreesoundError as err:
            self.failed.emit(str(err))


class WaveformWorker(QThread):
    """Downloads a sound's preview to the cache (if needed), decodes it and
    computes waveform peaks. Emits the sound id so late results for a
    previously selected sound can be discarded."""
    succeeded = Signal(int, list, object)  # sound id, peaks, DecodedAudio
    failed = Signal(int, str)

    def __init__(self, sound, parent=None):
        super().__init__(parent)
        self._sound = sound

    @staticmethod
    def cache_path(sound):
        return os.path.join(PREVIEW_CACHE_DIR, "%s.mp3" % sound["id"])

    def run(self):
        sid = self._sound["id"]
        try:
            path = self.cache_path(self._sound)
            if not os.path.isfile(path):
                os.makedirs(PREVIEW_CACHE_DIR, exist_ok=True)
                download_file(preview_url(self._sound), path)
            decoded = decode_file(path)
            self.succeeded.emit(sid, compute_peaks(decoded), decoded)
        except (FreesoundError, OSError) as err:
            self.failed.emit(sid, str(err))
