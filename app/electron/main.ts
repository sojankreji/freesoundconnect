/** Electron main process: window, media:// protocol, IPC surface. */
import * as fs from "fs";
import * as path from "path";
import { BrowserWindow, app, ipcMain, shell } from "electron";

import { DownloadManager, DownloadState } from "./downloads";
import { FreesoundError, searchSounds } from "./freesound-api";
import {
  AuthManager, buildAuthorizeUrl, extractCode, hasCredentials,
  waitForOAuthCode,
} from "./oauth";
import { DOWNLOAD_DIR } from "./paths";
import {
  Library, loadConfig, loadLibrary, logError, saveLibrary,
} from "./store";

const config = loadConfig();
const auth = new AuthManager(config);
let library: Library = loadLibrary();
let win: BrowserWindow | null = null;
let cancelLoginWait: (() => void) | null = null;

const downloads = new DownloadManager(config, auth,
  (state: DownloadState) => win?.webContents.send("fsc:downloadState", state));

/** Read a file into a transferable ArrayBuffer for IPC. */
function fileBytes(file: string): ArrayBuffer {
  const buf = fs.readFileSync(file);
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
}

function createWindow(): void {
  win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1000,
    minHeight: 660,
    backgroundColor: "#0b0e1f",
    title: "Freesound Connect",
    webPreferences: { preload: path.join(__dirname, "preload.js") },
  });
  win.on("closed", () => { win = null; });

  const devUrl = process.env["ELECTRON_START_URL"];
  if (devUrl && !app.isPackaged) {
    win.loadURL(devUrl);
  } else {
    win.loadFile(path.join(
      __dirname, "..", "dist", "freesoundconnect", "browser", "index.html"));
  }
}

/** Wrap IPC handlers so renderer gets {ok,value}|{ok:false,error}. */
function handle(channel: string,
                fn: (...args: any[]) => unknown): void {
  ipcMain.handle(channel, async (_event, ...args) => {
    try {
      return { ok: true, value: await fn(...args) };
    } catch (err: any) {
      if (!(err instanceof FreesoundError)) logError(channel, err);
      return { ok: false, error: String(err?.message ?? err) };
    }
  });
}

function broadcastAuth(): void {
  win?.webContents.send("fsc:authChanged", auth.state());
}

function commitLibrary(): void {
  saveLibrary(library);
  win?.webContents.send("fsc:libraryChanged", library);
}

// -- auth -------------------------------------------------------------------

handle("auth:getState", () => auth.state());
handle("auth:hasCredentials", () => hasCredentials());

handle("auth:login", () => {
  cancelLoginWait?.();
  const wait = waitForOAuthCode();
  cancelLoginWait = wait.cancel;
  shell.openExternal(buildAuthorizeUrl());
  wait.code
    .then(async (code) => {
      await auth.completeLogin(code);
      broadcastAuth();
      win?.webContents.send("fsc:loginResult", { ok: true });
    })
    .catch((err: any) => {
      const message = String(err?.message ?? err);
      if (message !== "cancelled") {
        win?.webContents.send("fsc:loginResult", { ok: false, error: message });
      }
    });
});

handle("auth:submitCode", async (text: string) => {
  cancelLoginWait?.();
  cancelLoginWait = null;
  await auth.completeLogin(extractCode(String(text).trim()));
  broadcastAuth();
  return auth.state();
});

handle("auth:cancelLogin", () => {
  cancelLoginWait?.();
  cancelLoginWait = null;
});

handle("auth:logout", () => {
  auth.logout();
  broadcastAuth();
});

// -- search -----------------------------------------------------------------

handle("search:run", async (params: any) => {
  const token = await auth.ensureValidToken();
  return searchSounds(token, params);
});

// -- audio files ------------------------------------------------------------

handle("sound:previewBytes", async (sound: any) => {
  const file = await downloads.ensurePreview(sound);
  return fileBytes(file);
});

handle("sound:prefetchOriginal", (sound: any) => {
  if (!auth.isLoggedIn()) return downloads.state(sound.id);
  downloads.ensureOriginal(sound).catch(() => { /* state is broadcast */ });
  return downloads.state(sound.id);
});

handle("sound:downloadState", (soundId: number) => downloads.state(soundId));

/** Cached original bytes for region decoding, or null if not downloaded. */
handle("sound:originalBytes", (sound: any) => {
  const file = downloads.originalPath(sound);
  return fs.existsSync(file) ? fileBytes(file) : null;
});

handle("region:save", (sound: any, startMs: number, endMs: number,
                       data: ArrayBuffer) => {
  downloads.saveRegionWav(sound, startMs, endMs, data);
  return true;
});

handle("region:exists", (sound: any, startMs: number, endMs: number) =>
  fs.existsSync(downloads.regionPath(sound, startMs, endMs)));

// -- drag out ---------------------------------------------------------------

handle("drag:start", (sound: any,
                      region: { startMs: number; endMs: number } | null) => {
  if (!auth.isLoggedIn()) {
    return { ok: false, reason: "Log in with Freesound first." };
  }
  const file = region
    ? downloads.regionPath(sound, region.startMs, region.endMs)
    : downloads.originalPath(sound);
  if (!fs.existsSync(file)) {
    const state = downloads.state(sound.id);
    if (state.phase !== "downloading") downloads.ensureOriginal(sound)
      .catch(() => { /* state is broadcast */ });
    return {
      ok: false,
      reason: region
        ? "Still exporting the selection — try dragging again in a moment."
        : "Still downloading the original — try dragging again in a moment.",
    };
  }
  win?.webContents.startDrag({
    file,
    icon: path.join(__dirname, "drag-icon.png"),
  });
  downloads.appendCredit(sound);
  return { ok: true };
});

// -- library ----------------------------------------------------------------

handle("library:get", () => library);

handle("library:addShot", (sound: any) => {
  if (library.shotlist.some((s) => s.id === sound.id)) return false;
  library.shotlist.push(sound);
  commitLibrary();
  return true;
});

handle("library:removeShot", (soundId: number) => {
  library.shotlist = library.shotlist.filter((s) => s.id !== soundId);
  commitLibrary();
});

handle("library:clearShot", () => {
  library.shotlist = [];
  commitLibrary();
});

handle("library:savePlaylist", (name: string, sounds: any[]) => {
  library.playlists[name] = [...sounds];
  commitLibrary();
});

handle("library:deletePlaylist", (name: string) => {
  delete library.playlists[name];
  commitLibrary();
});

handle("library:renamePlaylist", (oldName: string, newName: string) => {
  if (!(oldName in library.playlists) || newName in library.playlists) {
    return false;
  }
  library.playlists[newName] = library.playlists[oldName];
  delete library.playlists[oldName];
  commitLibrary();
  return true;
});

handle("library:removeFromPlaylist", (name: string, soundId: number) => {
  const sounds = library.playlists[name];
  if (!sounds) return;
  library.playlists[name] = sounds.filter((s) => s.id !== soundId);
  commitLibrary();
});

// -- misc -------------------------------------------------------------------

handle("app:openExternal", (url: string) => {
  if (/^https?:\/\//.test(url)) shell.openExternal(url);
});

handle("app:openDownloads", () => {
  fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });
  shell.openPath(downloads.dir());
});

// -- lifecycle --------------------------------------------------------------

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
