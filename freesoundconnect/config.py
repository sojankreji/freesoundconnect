"""Configuration, paths, constants and error logging."""

import json
import os
import time
import traceback

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
SEARCH_FIELDS = (
    "id,name,previews,duration,username,license,url,type,samplerate,"
    "channels,bitdepth,filesize,num_downloads,avg_rating,num_ratings,"
    "tags,description,created"
)

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".freesoundconnect")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.join(CONFIG_DIR, "error.log")
PLAYLISTS_PATH = os.path.join(CONFIG_DIR, "playlists.json")
PREVIEW_CACHE_DIR = os.path.join(CONFIG_DIR, "previews")
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


def load_playlists():
    try:
        with open(PLAYLISTS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            data.setdefault("shotlist", [])
            data.setdefault("playlists", {})
            return data
    except (OSError, ValueError):
        pass
    return {"shotlist": [], "playlists": {}}


def save_playlists(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(PLAYLISTS_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def log_error(context, err):
    """Best-effort debug log — packaged windowed apps have no visible
    console, so unexpected errors would otherwise vanish silently."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("[%s] %s: %s\n" % (
                time.strftime("%Y-%m-%d %H:%M:%S"), context, err))
            if isinstance(err, BaseException) and err.__traceback__:
                fh.write(traceback.format_exc())
                fh.write("\n")
    except OSError:
        pass
