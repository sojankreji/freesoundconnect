/** Preview cache, original-quality downloads, region WAVs, CREDITS.txt. */
import * as fs from "fs";
import * as path from "path";

import {
  downloadToFile, originalDownloadUrl, originalFilename, previewUrl,
  sanitizeFilename,
} from "./freesound-api";
import { AuthManager } from "./oauth";
import { PREVIEW_CACHE_DIR } from "./paths";
import { AppConfig, downloadDir, logError } from "./store";

export type DownloadPhase = "idle" | "downloading" | "ready" | "error";

export interface DownloadState {
  soundId: number;
  phase: DownloadPhase;
  progress: number;
  error?: string;
}

/**
 * Tracks per-sound original downloads so the UI can show readiness and
 * drags can start instantly once a file is cached.
 */
export class DownloadManager {
  private states = new Map<number, DownloadState>();
  private inflight = new Map<number, Promise<string>>();

  constructor(
    private config: AppConfig,
    private auth: AuthManager,
    private broadcast: (state: DownloadState) => void,
  ) {}

  dir(): string {
    return downloadDir(this.config);
  }

  previewPath(soundId: number): string {
    return path.join(PREVIEW_CACHE_DIR, `${soundId}.mp3`);
  }

  originalPath(sound: any): string {
    return path.join(this.dir(), originalFilename(sound));
  }

  regionPath(sound: any, startMs: number, endMs: number): string {
    return path.join(this.dir(),
      `${sound.id}__${sanitizeFilename(sound.name)}__${startMs}ms-${endMs}ms.wav`);
  }

  state(soundId: number): DownloadState {
    return this.states.get(soundId) ??
      { soundId, phase: "idle", progress: 0 };
  }

  private setState(state: DownloadState): void {
    this.states.set(state.soundId, state);
    this.broadcast(state);
  }

  /** Download the preview MP3 into the cache (no auth needed). */
  async ensurePreview(sound: any): Promise<string> {
    const dest = this.previewPath(sound.id);
    if (!fs.existsSync(dest)) {
      await downloadToFile(previewUrl(sound), dest);
    }
    return dest;
  }

  /**
   * Ensure the original-quality file exists locally, downloading in the
   * background if needed. Repeated calls while downloading return the
   * same promise.
   */
  ensureOriginal(sound: any): Promise<string> {
    const dest = this.originalPath(sound);
    if (fs.existsSync(dest)) {
      if (this.state(sound.id).phase !== "ready") {
        this.setState({ soundId: sound.id, phase: "ready", progress: 1 });
      }
      return Promise.resolve(dest);
    }
    const existing = this.inflight.get(sound.id);
    if (existing) return existing;

    const task = (async () => {
      this.setState({ soundId: sound.id, phase: "downloading", progress: 0 });
      try {
        const token = await this.auth.ensureValidToken();
        await downloadToFile(originalDownloadUrl(sound), dest, token,
          (fraction) => this.setState({
            soundId: sound.id, phase: "downloading", progress: fraction,
          }));
        this.setState({ soundId: sound.id, phase: "ready", progress: 1 });
        return dest;
      } catch (err: any) {
        logError("download_original", err);
        this.setState({
          soundId: sound.id, phase: "error", progress: 0,
          error: String(err?.message ?? err),
        });
        throw err;
      } finally {
        this.inflight.delete(sound.id);
      }
    })();
    this.inflight.set(sound.id, task);
    return task;
  }

  /** Persist a renderer-encoded region WAV next to the other downloads. */
  saveRegionWav(sound: any, startMs: number, endMs: number,
                data: ArrayBuffer): string {
    const dest = this.regionPath(sound, startMs, endMs);
    fs.mkdirSync(this.dir(), { recursive: true });
    fs.writeFileSync(dest, Buffer.from(data));
    return dest;
  }

  /** Attribution list — most Freesound sounds are CC and CC-BY needs credit. */
  appendCredit(sound: any): void {
    const creditsPath = path.join(this.dir(), "CREDITS.txt");
    const line = `"${sound.name}" by ${sound.username} — ` +
      `${sound.url ?? `https://freesound.org/s/${sound.id}/`} — ` +
      `License: ${sound.license}\n`;
    try {
      fs.mkdirSync(this.dir(), { recursive: true });
      const existing = fs.existsSync(creditsPath)
        ? fs.readFileSync(creditsPath, "utf-8") : "";
      if (!existing.includes(line)) fs.appendFileSync(creditsPath, line);
    } catch {
      /* attribution file is best-effort */
    }
  }
}
