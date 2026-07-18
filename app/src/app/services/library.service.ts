import { Injectable, computed, signal } from '@angular/core';

import { Sound } from '../models/sound';
import { Library, fsc } from './fsc';
import { ToastService } from './toast.service';

@Injectable({ providedIn: 'root' })
export class LibraryService {
  readonly library = signal<Library>({ shotlist: [], playlists: {} });
  readonly shotlist = computed(() => this.library().shotlist);
  readonly shotCount = computed(() => this.library().shotlist.length);
  readonly playlistNames = computed(() => Object.keys(this.library().playlists).sort());

  constructor(private toast: ToastService) {
    const api = fsc();
    if (!api) return;
    api.library.get().then((lib) => this.library.set(lib));
    api.library.onChanged((lib) => this.library.set(lib));
  }

  inShotlist(soundId: number): boolean {
    return this.library().shotlist.some((s) => s.id === soundId);
  }

  async addShot(sound: Sound): Promise<void> {
    const added = await fsc()?.library.addShot(sound);
    this.toast.info(added
      ? `Added “${sound.name}” to the shotlist.`
      : `“${sound.name}” is already in the shotlist.`);
  }

  removeShot(soundId: number): Promise<void> | void {
    return fsc()?.library.removeShot(soundId);
  }

  clearShot(): Promise<void> | void {
    return fsc()?.library.clearShot();
  }

  playlist(name: string): Sound[] {
    return this.library().playlists[name] ?? [];
  }

  hasPlaylist(name: string): boolean {
    return name in this.library().playlists;
  }

  async savePlaylist(name: string, sounds: Sound[]): Promise<void> {
    await fsc()?.library.savePlaylist(name, sounds);
    this.toast.info(`Saved playlist “${name}” (${sounds.length} sounds).`);
  }

  async deletePlaylist(name: string): Promise<void> {
    await fsc()?.library.deletePlaylist(name);
    this.toast.info(`Deleted playlist “${name}”.`);
  }

  async renamePlaylist(oldName: string, newName: string): Promise<boolean> {
    const ok = await fsc()?.library.renamePlaylist(oldName, newName);
    if (ok) this.toast.info(`Renamed “${oldName}” to “${newName}”.`);
    else this.toast.error(`A playlist named “${newName}” already exists.`);
    return !!ok;
  }

  removeFromPlaylist(name: string, soundId: number): Promise<void> | void {
    return fsc()?.library.removeFromPlaylist(name, soundId);
  }
}
