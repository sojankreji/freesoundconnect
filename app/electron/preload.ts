/** Context bridge: the typed `window.fsc` API the Angular app talks to. */
import { contextBridge, ipcRenderer } from "electron";

type Unsubscribe = () => void;

async function invoke<T>(channel: string, ...args: unknown[]): Promise<T> {
  const result = await ipcRenderer.invoke(channel, ...args);
  if (!result.ok) throw new Error(result.error);
  return result.value as T;
}

function subscribe(channel: string,
                   callback: (payload: any) => void): Unsubscribe {
  const listener = (_event: unknown, payload: any) => callback(payload);
  ipcRenderer.on(channel, listener);
  return () => ipcRenderer.removeListener(channel, listener);
}

const api = {
  auth: {
    getState: () => invoke<any>("auth:getState"),
    hasCredentials: () => invoke<boolean>("auth:hasCredentials"),
    login: () => invoke<void>("auth:login"),
    submitCode: (text: string) => invoke<any>("auth:submitCode", text),
    cancelLogin: () => invoke<void>("auth:cancelLogin"),
    logout: () => invoke<void>("auth:logout"),
    onChanged: (cb: (state: any) => void) => subscribe("fsc:authChanged", cb),
    onLoginResult: (cb: (result: any) => void) =>
      subscribe("fsc:loginResult", cb),
  },
  search: {
    run: (params: any) => invoke<any>("search:run", params),
  },
  sound: {
    previewBytes: (sound: any) =>
      invoke<ArrayBuffer>("sound:previewBytes", sound),
    prefetchOriginal: (sound: any) =>
      invoke<any>("sound:prefetchOriginal", sound),
    downloadState: (soundId: number) =>
      invoke<any>("sound:downloadState", soundId),
    originalBytes: (sound: any) =>
      invoke<ArrayBuffer | null>("sound:originalBytes", sound),
    onDownloadState: (cb: (state: any) => void) =>
      subscribe("fsc:downloadState", cb),
  },
  region: {
    save: (sound: any, startMs: number, endMs: number, data: ArrayBuffer) =>
      invoke<boolean>("region:save", sound, startMs, endMs, data),
    exists: (sound: any, startMs: number, endMs: number) =>
      invoke<boolean>("region:exists", sound, startMs, endMs),
  },
  drag: {
    start: (sound: any, region: { startMs: number; endMs: number } | null) =>
      invoke<{ ok: boolean; reason?: string }>("drag:start", sound, region),
  },
  library: {
    get: () => invoke<any>("library:get"),
    addShot: (sound: any) => invoke<boolean>("library:addShot", sound),
    removeShot: (soundId: number) =>
      invoke<void>("library:removeShot", soundId),
    clearShot: () => invoke<void>("library:clearShot"),
    savePlaylist: (name: string, sounds: any[]) =>
      invoke<void>("library:savePlaylist", name, sounds),
    deletePlaylist: (name: string) =>
      invoke<void>("library:deletePlaylist", name),
    renamePlaylist: (oldName: string, newName: string) =>
      invoke<boolean>("library:renamePlaylist", oldName, newName),
    removeFromPlaylist: (name: string, soundId: number) =>
      invoke<void>("library:removeFromPlaylist", name, soundId),
    onChanged: (cb: (library: any) => void) =>
      subscribe("fsc:libraryChanged", cb),
  },
  app: {
    openExternal: (url: string) => invoke<void>("app:openExternal", url),
    openDownloads: () => invoke<void>("app:openDownloads"),
  },
};

contextBridge.exposeInMainWorld("fsc", api);

export type FscApi = typeof api;
