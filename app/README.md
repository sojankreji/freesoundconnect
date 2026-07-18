# Freesound Connect (Electron + Angular)

The desktop app: search [freesound.org](https://freesound.org), preview sounds
with an interactive waveform, and **drag them (or a selected region) straight
onto your DaVinci Resolve timeline**.

User data lives under `~/.freesoundconnect/` (OAuth tokens, shotlist, playlists)
and downloads under `~/Documents/FreesoundConnect/`.

## Architecture

- **Electron main** (`electron/`, TypeScript → `dist-electron/`): all
  Freesound HTTP, OAuth2, file downloads, region-WAV writing, and the native
  OS drag-out (`webContents.startDrag`). No network or tokens ever reach the
  renderer.
  - `oauth.ts` — browser login via loopback `127.0.0.1:8918/callback`, manual
    code-paste fallback, token refresh.
  - `freesound-api.ts` — search/profile/download.
  - `downloads.ts` — preview cache, original-quality downloads with progress,
    `CREDITS.txt`, region WAVs.
  - `preload.ts` — the typed `window.fsc` bridge (contextIsolation on).
- **Angular renderer** (`src/`, standalone components + signals): the UI —
  nav sidebar (Search / Playlists), search results with rich detail columns,
  the wavesurfer.js player bar with drag-to-select regions, the 🛒 shotlist
  cart popover, and the Playlists page. Audio is streamed to the renderer as
  bytes over IPC and played via a `blob:` URL, so region export can decode the
  exact same data with the Web Audio API.

## Develop

Requires Node 22.12+ / 24.15+ (Angular 21). From `app/`:

```bash
npm install
npm run dev        # ng serve + Electron with live reload
```

`npm run dev` needs OAuth credentials — either set `FREESOUND_CLIENT_ID` /
`FREESOUND_CLIENT_SECRET`, or copy `electron/credentials.example.json` to
`electron/credentials.json` (gitignored).

## Build & package

```bash
npm run build      # Angular production build + compile Electron main
npm run dist       # the above, then electron-builder → app/release/
```

`electron-builder` produces a dmg/zip (macOS), nsis installer (Windows), and
AppImage (Linux). CI ([.github/workflows/electron-build.yml](../.github/workflows/electron-build.yml))
builds all three on a `v*` tag and attaches them to a GitHub Release; it writes
`electron/credentials.json` from repo secrets `FREESOUND_CLIENT_ID` /
`FREESOUND_CLIENT_SECRET`.

## Data

Under `~/.freesoundconnect/`:

| File | Purpose |
|------|---------|
| `config.json` | OAuth tokens (chmod 600) |
| `playlists.json` | `{ shotlist: [], playlists: {} }` |
| `previews/` | cached preview MP3s |

Downloads (original files, region WAVs, `CREDITS.txt`) go to
`~/Documents/FreesoundConnect/`.
