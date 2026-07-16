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
  real audio file
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
[**Releases page**](https://github.com/YOUR_USERNAME/freesound-connect/releases)
— no Python required:

| OS | File | Notes |
|----|------|-------|
| macOS | `FreesoundConnect-macOS.zip` | Unzip, move to Applications. First launch: **right-click ▸ Open** (the app is unsigned), or run `xattr -dr com.apple.quarantine "/Applications/Freesound Connect.app"` |
| Windows | `FreesoundConnect-Windows.zip` | Unzip and run `FreesoundConnect.exe`. SmartScreen may warn about an unsigned app — choose *More info ▸ Run anyway* |
| Linux | `FreesoundConnect-Linux.zip` | Unzip, `chmod +x freesound-connect`, run it |

All you need besides the app is a free Freesound API key (setup below —
takes ~2 minutes).

## Running from source

Requires Python 3.9+:

```bash
git clone https://github.com/YOUR_USERNAME/freesound-connect
cd freesound-connect
pip3 install -r requirements.txt
python3 freesound_connect.py
```

Or install it as a command with [pipx](https://pipx.pypa.io):

```bash
pipx install .
freesound-connect
```

## Getting a Freesound API key

1. Create a free account at [freesound.org](https://freesound.org).
2. Go to <https://freesound.org/apiv2/apply/> and request an API key.
   Any name and description will do (e.g. "Freesound Connect");
   leave the OAuth2 fields empty — this app only needs the simple
   **token** key.
3. The first time you launch the app it will ask for the key. Paste it and
   hit **Save**. It's stored locally in `~/.freesound-connect/config.json`
   and never sent anywhere except to freesound.org.

You can change the key any time with the **API Key…** button.

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

- **Audio quality:** sounds are fetched as Freesound's high-quality MP3
  previews (~128 kbps). Downloading the *original* uncompressed files
  requires OAuth2 login, which is on the roadmap. For most SFX/ambience
  use the HQ preview is indistinguishable in a mix.
- **Licenses:** filter by **CC0** if you want zero-attribution sounds for
  commercial work. CC-BY requires credit (the app writes it for you);
  CC-BY-NC is non-commercial only. You are responsible for complying with
  each sound's license.

## Troubleshooting

- **"Freesound Connect needs PySide6"** — run
  `pip3 install -r requirements.txt` with the same Python you use to start
  the app.
- **"Invalid API key (401)"** — Re-copy the key from
  <https://freesound.org/apiv2/apply/> (it's the *Client secret/API key*
  value) and re-enter it via **API Key…**.
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

## Roadmap

- Code-signed / notarized builds
- OAuth2 support for original-quality downloads
- Waveform display and scrub preview
- Duration / sample-rate filters, tag browsing
- Optional direct insert-at-playhead for Resolve **Studio** (scripting API)

Contributions welcome — open an issue or PR!

## License

[MIT](LICENSE). Not affiliated with Blackmagic Design or the Freesound
project. Sound content is subject to each sound's own Creative Commons
license and the [Freesound API terms](https://freesound.org/help/tos_api/).
