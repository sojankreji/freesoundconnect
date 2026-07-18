import { ChangeDetectionStrategy, Component, computed, effect, signal } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';

import { SoundList } from '../components/sound-list';
import { Sound } from '../models/sound';
import { LibraryService } from '../services/library.service';
import { PlayerService } from '../services/player.service';

@Component({
  selector: 'app-playlists-page',
  standalone: true,
  imports: [LucideAngularModule, SoundList],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './playlists-page.html',
  styleUrl: './playlists-page.css',
})
export class PlaylistsPage {
  readonly selectedName = signal<string | null>(null);
  readonly names;
  readonly sounds;

  constructor(private library: LibraryService, private player: PlayerService) {
    this.names = library.playlistNames;
    this.sounds = computed(() => {
      const name = this.selectedName();
      return name ? library.playlist(name) : [];
    });

    // Keep a valid selection as playlists change (rename/delete/first load).
    effect(() => {
      const names = this.names();
      const current = this.selectedName();
      if (names.length === 0) {
        if (current !== null) this.selectedName.set(null);
      } else if (!current || !names.includes(current)) {
        this.selectedName.set(names[0]);
      }
    });
  }

  select(name: string): void {
    this.selectedName.set(name);
  }

  rename(): void {
    const old = this.selectedName();
    if (!old) return;
    const next = prompt('New name:', old)?.trim();
    if (!next || next === old) return;
    void this.library.renamePlaylist(old, next).then((ok) => {
      if (ok) this.selectedName.set(next);
    });
  }

  deletePlaylist(): void {
    const name = this.selectedName();
    if (name && confirm(`Delete the playlist “${name}”? (The shotlist is not affected.)`)) {
      void this.library.deletePlaylist(name);
    }
  }

  removeSound(): void {
    const name = this.selectedName();
    const sound = this.player.current();
    if (name && sound) void this.library.removeFromPlaylist(name, sound.id);
  }

  countFor(name: string): number {
    return this.library.playlist(name).length;
  }
}
