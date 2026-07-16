<p align="center">
  <img src="assets/icon.png" width="128" alt="Freesound Connect logo">
</p>

<h1 align="center">Freesound Connect for DaVinci Resolve</h1>

A standalone companion app: search [freesound.org](https://freesound.org),
preview sounds, and **drag them straight onto your DaVinci Resolve
timeline**.

- 🔎 Full-text search with license and sort filters
- ▶️ Instant in-app preview (double-click a result)
- 🎬 Drag any result onto Resolve's timeline or Media Pool — it lands as a
  real, **original-quality** audio file
- 🔐 One-click **"Log in with Freesound"** — no manual API keys to copy
- 📝 Automatically maintains a `CREDITS.txt` attribution file for the
  Creative Commons sounds you use
- 🆓 Works with **both the free version of DaVinci Resolve and Studio**
  (macOS, Windows, Linux)

## Why a standalone app?

Blackmagic removed script GUIs (Fusion UIManager) from the free version of
Resolve in 19.1, and external scripting has always been Studio-only. OS
drag-and-drop, however, works in every version of Resolve — so Freesound
Connect runs as its own window next to Resolve and hands files over the
same way Finder/Explorer does.

## Download

Grab the latest build for your OS from the
[**Releases page**](https://github.com/sojankreji/freesoundconnect/releases)
— no Python required:

| OS | File | Notes |
|----|------|-------|
| macOS | `FreesoundConnect-macOS.zip` | Unzip, move to Applications. First launch: **right-click ▸ Open** (the app is unsigned), or run `xattr -dr com.apple.quarantine "/Applications/Freesound Connect.app"` |
| Windows | `FreesoundConnect-Windows.zip` | Unzip and run `FreesoundConnect.exe`. SmartScreen may warn about an unsigned app — choose *More info ▸ Run anyway* |
| Linux | `FreesoundConnect-Linux.zip` | Unzip, `chmod +x freesoundconnect`, run it |

All you need besides the app is a free Freesound account — clicking
**Log in with Freesound** in the app handles the rest.

## Running from source

Requires Python 3.9+:

```bash
git clone https://github.com/sojankreji/freesoundconnect
cd freesoundconnect
pip3 install -r requirements.txt
python3 freesound_connect.py
```

Or install it as a command with [pipx](https://pipx.pypa.io):

```bash
pipx install .
freesoundconnect
```

Running from source needs its own OAuth credentials — see
[Setting up OAuth credentials](#setting-up-oauth-credentials-for-maintainers)
below, or ask whoever maintains your fork for a dev
`oauth_credentials.py`.

## Logging in

Freesound Connect signs you in with your real Freesound account via OAuth2
— there's no API key to find or paste.

1. Launch the app and click **Log in with Freesound**.
2. Your browser opens Freesound's login/authorize page. Approve access.
3. The tab confirms you're logged in — switch back to Freesound Connect,
   where your avatar and username now appear in the header.

Tokens are stored locally in `~/.freesoundconnect/config.json`
(file permissions restricted to your user) and refreshed automatically.
Click **Log out** any time to revoke local access — this doesn't revoke
the authorization on freesound.org itself, which you can do from your
[Freesound account settings](https://freesound.org/home/app_permissions/).

## Usage

1. Launch the app and keep it next to (or on top of) Resolve.
2. Type a search term ("rain", "whoosh", "door slam"…) and press Enter.
   Optionally filter by license (CC0 / CC-BY / CC-BY-NC) and sort order.
3. Double-click a result (or hit **▶ Preview**) to listen.
4. **Drag the row onto your Resolve timeline** — drop it on an audio track
   at the spot you want, or drop it in the Media Pool. Selecting a row
   pre-downloads it in the background, so drags are instant.

Sounds are saved to `~/Documents/FreesoundConnect/` — keep that folder
around, since your Resolve project links to the files in it. Every sound
you take is also logged to `CREDITS.txt` in that folder with its author,
URL, and license — paste it straight into your video description to
satisfy CC-BY attribution.

## Good to know

- **Audio quality:** in-app preview streams Freesound's compressed MP3
  preview, but **dragging to the timeline downloads the original file**
  exactly as its uploader submitted it (WAV/AIFF/FLAC/etc.) — this needs
  the OAuth2 login above, which is why login is required before searching.
- **Licenses:** filter by **CC0** if you want zero-attribution sounds for
  commercial work. CC-BY requires credit (the app writes it for you);
  CC-BY-NC is non-commercial only. You are responsible for complying with
  each sound's license.

## Troubleshooting

- **"Freesound Connect needs PySide6"** — run
  `pip3 install -r requirements.txt` with the same Python you use to start
  the app.
- **"This build is missing Freesound OAuth credentials"** — you're running
  from source without an `oauth_credentials.py`. See
  [Setting up OAuth credentials](#setting-up-oauth-credentials-for-maintainers).
- **Browser opens but the app never logs you in** — something else on
  your machine is using port 8918. Quit it and click **Log in with
  Freesound** again (the port is currently fixed; see Roadmap).
- **"Your Freesound login expired"** — click **Log in with Freesound**
  again; refresh tokens can be revoked from your
  [Freesound account settings](https://freesound.org/home/app_permissions/).
- **Browser redirect doesn't come back / login seems to hang** — in the
  login window that opens, paste the authorization code (or the whole
  address-bar URL after you approve) into the **"Paste authorization
  code…"** field and click **Submit code**. This bypasses the local
  redirect entirely, which is useful if a firewall or unusual browser
  setup blocks `127.0.0.1:8918`. Unexpected login errors are also logged
  to `~/.freesoundconnect/error.log`.
- **No sound on preview (Linux)** — Qt Multimedia needs GStreamer plugins:
  `sudo apt install gstreamer1.0-plugins-good gstreamer1.0-plugins-bad libmpg123-0`.
- **"SSL certificates missing"** — Your Python can't verify HTTPS
  certificates (common with python.org installs on macOS). Run
  `pip3 install certifi`, or run *Install Certificates.command* found in
  your `/Applications/Python 3.x/` folder.

## Building executables

Releases are built automatically by
[GitHub Actions](.github/workflows/build.yml): pushing a tag like `v1.0.0`
builds macOS, Windows, and Linux executables with PyInstaller and attaches
them to a GitHub Release. To build locally:

```bash
pip3 install -r requirements.txt pyinstaller
./scripts/build.sh        # macOS / Linux  →  dist/
.\scripts\build.ps1       # Windows        →  dist\FreesoundConnect.exe
```

The logo lives in [assets/icon.svg](assets/icon.svg); regenerate the
`.png` / `.icns` / `.ico` derivatives with
`python3 scripts/render_icons.py` (needs PySide6 + Pillow).

## Setting up OAuth credentials (for maintainers)

Freesound Connect uses a single, shared "Log in with Freesound" OAuth2
app — end users never register anything themselves. If you're building
the app yourself (from source or for a release), you need your own
Freesound app credentials:

1. Log in at [freesound.org](https://freesound.org) and go to
   <https://freesound.org/apiv2/apps/> to create a new API credential.
2. Set its **Redirect URI** to exactly `http://127.0.0.1:8918/callback`
   — this must match `REDIRECT_URI` in `freesound_connect.py`.
3. Copy `oauth_credentials.example.py` to `oauth_credentials.py` (already
   gitignored) and fill in the `CLIENT_ID` / `CLIENT_SECRET` you were
   given:
   ```bash
   cp oauth_credentials.example.py oauth_credentials.py
   ```
4. Run the app normally — it picks up `oauth_credentials.py`
   automatically. (You can alternatively set the `FREESOUND_CLIENT_ID`
   / `FREESOUND_CLIENT_SECRET` environment variables instead of the
   file.)

For CI-built releases, add `FREESOUND_CLIENT_ID` and
`FREESOUND_CLIENT_SECRET` as **repository secrets** in GitHub (Settings
▸ Secrets and variables ▸ Actions) — the
[build workflow](.github/workflows/build.yml) writes them into
`oauth_credentials.py` before each build so the secret itself never
touches the git history.

`CLIENT_SECRET` does end up embedded in the distributed executables —
that's inherent to how desktop OAuth2 clients work and is what
Freesound's own API expects for non-server apps.

## Roadmap

- Code-signed / notarized builds
- Configurable OAuth redirect port (currently fixed at 8918)
- Waveform display and scrub preview
- Duration / sample-rate filters, tag browsing
- Optional direct insert-at-playhead for Resolve **Studio** (scripting API)

Contributions welcome — open an issue or PR!

## License

[MIT](LICENSE). Not affiliated with Blackmagic Design or the Freesound
project. Sound content is subject to each sound's own Creative Commons
license and the [Freesound API terms](https://freesound.org/help/tos_api/).
