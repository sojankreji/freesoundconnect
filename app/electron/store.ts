/** Persistence for config (OAuth tokens) and the shotlist/playlists. */
import * as fs from "fs";

import {
  CONFIG_DIR, CONFIG_PATH, DOWNLOAD_DIR, LOG_PATH, PLAYLISTS_PATH,
} from "./paths";

export interface OAuthData {
  access_token?: string;
  refresh_token?: string;
  expires_at?: number;
  username?: string;
  avatar_url?: string;
}

export interface AppConfig {
  oauth?: OAuthData;
  download_dir?: string;
  [key: string]: unknown;
}

export interface Library {
  shotlist: any[];
  playlists: Record<string, any[]>;
}

function readJson<T>(file: string, fallback: T): T {
  try {
    return { ...fallback, ...JSON.parse(fs.readFileSync(file, "utf-8")) };
  } catch {
    return fallback;
  }
}

function writeJson(file: string, data: unknown, mode?: number): void {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2), "utf-8");
  if (mode !== undefined) {
    try {
      fs.chmodSync(file, mode);
    } catch {
      /* best effort */
    }
  }
}

export function loadConfig(): AppConfig {
  return readJson<AppConfig>(CONFIG_PATH, {});
}

export function saveConfig(cfg: AppConfig): void {
  writeJson(CONFIG_PATH, cfg, 0o600);
}

export function loadLibrary(): Library {
  return readJson<Library>(PLAYLISTS_PATH, { shotlist: [], playlists: {} });
}

export function saveLibrary(lib: Library): void {
  writeJson(PLAYLISTS_PATH, lib);
}

/** Best-effort debug log — packaged apps have no visible console. */
export function logError(context: string, err: unknown): void {
  try {
    fs.mkdirSync(CONFIG_DIR, { recursive: true });
    const stamp = new Date().toISOString().replace("T", " ").slice(0, 19);
    const detail = err instanceof Error ? `${err.message}\n${err.stack}` : String(err);
    fs.appendFileSync(LOG_PATH, `[${stamp}] ${context}: ${detail}\n`);
  } catch {
    /* best effort */
  }
}

export function downloadDir(cfg: AppConfig): string {
  return cfg.download_dir ?? DOWNLOAD_DIR;
}
