"""Freesound HTTP API client and formatting helpers."""

import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from . import APP_NAME, VERSION
from .config import API_BASE, PAGE_SIZE, SEARCH_FIELDS


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
                   license_filter=None, extra_filter=None):
    params = {
        "query": query,
        "page": page,
        "page_size": PAGE_SIZE,
        "fields": SEARCH_FIELDS,
        "sort": sort,
    }
    filters = []
    if license_filter:
        filters.append("license:%s" % license_filter)
    if extra_filter:
        filters.append(extra_filter)
    if filters:
        params["filter"] = " ".join(filters)
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


def format_specs(sound):
    parts = []
    rate = sound.get("samplerate")
    if rate:
        parts.append("%g kHz" % (float(rate) / 1000.0))
    channels = sound.get("channels")
    if channels:
        parts.append({1: "mono", 2: "stereo"}.get(channels,
                                                  "%dch" % channels))
    depth = sound.get("bitdepth")
    if depth:
        parts.append("%d-bit" % depth)
    return " · ".join(parts)


def format_rating(sound):
    num = sound.get("num_ratings") or 0
    if not num:
        return "—"
    return "★ %.1f (%d)" % (sound.get("avg_rating") or 0.0, num)


def format_filesize(nbytes):
    try:
        nbytes = float(nbytes)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return ("%.1f %s" if unit != "B" else "%d %s") % (nbytes, unit)
        nbytes /= 1024.0


def sound_tooltip(sound):
    lines = [sound.get("name", "")]
    desc = (sound.get("description") or "").strip()
    if desc:
        if len(desc) > 400:
            desc = desc[:400] + "…"
        lines.append("")
        lines.append(desc)
    tags = sound.get("tags") or []
    if tags:
        lines.append("")
        lines.append("Tags: " + ", ".join(tags[:15]))
    meta = []
    size = format_filesize(sound.get("filesize"))
    if size:
        meta.append(size)
    created = (sound.get("created") or "")[:10]
    if created:
        meta.append("uploaded " + created)
    if meta:
        lines.append("")
        lines.append(" · ".join(meta))
    return "\n".join(lines)


def short_license(url):
    return (url or "").replace(
        "http://creativecommons.org/licenses/", "CC ").replace(
        "https://creativecommons.org/licenses/", "CC ").replace(
        "http://creativecommons.org/publicdomain/zero/1.0/", "CC0").replace(
        "https://creativecommons.org/publicdomain/zero/1.0/", "CC0")
