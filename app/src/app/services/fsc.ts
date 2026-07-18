/** Access to the typed `window.fsc` bridge exposed by the Electron preload. */
import { Sound } from '../models/sound';

export interface AuthState {
  loggedIn: boolean;
  username: string | null;
  avatarUrl: string | null;
}

export interface DownloadState {
  soundId: number;
  phase: 'idle' | 'downloading' | 'ready' | 'error';
  progress: number;
  error?: string;
}

export interface Library {
  shotlist: Sound[];
  playlists: Record<string, Sound[]>;
}

export interface SearchParams {
  query: string;
  page: number;
  sort: string;
  licenseFilter?: string | null;
  extraFilter?: string | null;
}

export interface RegionMs {
  startMs: number;
  endMs: number;
}

type Unsubscribe = () => void;

export interface FscApi {
  auth: {
    getState(): Promise<AuthState>;
    hasCredentials(): Promise<boolean>;
    login(): Promise<void>;
    submitCode(text: string): Promise<AuthState>;
    cancelLogin(): Promise<void>;
    logout(): Promise<void>;
    onChanged(cb: (state: AuthState) => void): Unsubscribe;
    onLoginResult(cb: (result: { ok: boolean; error?: string }) => void): Unsubscribe;
  };
  search: {
    run(params: SearchParams): Promise<{ count: number; results: Sound[] }>;
  };
  sound: {
    previewBytes(sound: Sound): Promise<ArrayBuffer>;
    prefetchOriginal(sound: Sound): Promise<DownloadState>;
    downloadState(soundId: number): Promise<DownloadState>;
    originalBytes(sound: Sound): Promise<ArrayBuffer | null>;
    onDownloadState(cb: (state: DownloadState) => void): Unsubscribe;
  };
  region: {
    save(sound: Sound, startMs: number, endMs: number, data: ArrayBuffer): Promise<boolean>;
    exists(sound: Sound, startMs: number, endMs: number): Promise<boolean>;
  };
  drag: {
    start(sound: Sound, region: RegionMs | null): Promise<{ ok: boolean; reason?: string }>;
  };
  library: {
    get(): Promise<Library>;
    addShot(sound: Sound): Promise<boolean>;
    removeShot(soundId: number): Promise<void>;
    clearShot(): Promise<void>;
    savePlaylist(name: string, sounds: Sound[]): Promise<void>;
    deletePlaylist(name: string): Promise<void>;
    renamePlaylist(oldName: string, newName: string): Promise<boolean>;
    removeFromPlaylist(name: string, soundId: number): Promise<void>;
    onChanged(cb: (library: Library) => void): Unsubscribe;
  };
  app: {
    openExternal(url: string): Promise<void>;
    openDownloads(): Promise<void>;
  };
}

/** Null when the renderer runs outside Electron (e.g. plain `ng serve`). */
export function fsc(): FscApi | null {
  return (window as unknown as { fsc?: FscApi }).fsc ?? null;
}
