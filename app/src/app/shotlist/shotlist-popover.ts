import { ChangeDetectionStrategy, Component, computed, output } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';

import { Sound, fmtDuration } from '../models/sound';
import { DragService } from '../services/drag.service';
import { LibraryService } from '../services/library.service';
import { PlayerService } from '../services/player.service';

@Component({
  selector: 'app-shotlist-popover',
  standalone: true,
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './shotlist-popover.html',
  styleUrl: './shotlist-popover.css',
})
export class ShotlistPopover {
  readonly close = output<void>();

  readonly sounds = computed(() => this.library.shotlist());
  readonly fmtDuration = fmtDuration;

  constructor(
    private library: LibraryService,
    private player: PlayerService,
    private drag: DragService,
  ) {}

  isCurrent(sound: Sound): boolean {
    return this.player.current()?.id === sound.id;
  }

  isPlaying(sound: Sound): boolean {
    return this.isCurrent(sound) && this.player.playing();
  }

  load(sound: Sound): void {
    this.player.select(sound);
  }

  play(event: Event, sound: Sound): void {
    event.stopPropagation();
    this.player.play(sound);
  }

  remove(event: Event, sound: Sound): void {
    event.stopPropagation();
    void this.library.removeShot(sound.id);
  }

  onDragStart(event: DragEvent, sound: Sound): void {
    void this.drag.begin(event, sound);
  }

  clear(): void {
    if (this.sounds().length && confirm('Remove all sounds from the shotlist?')) {
      void this.library.clearShot();
    }
  }

  saveAsPlaylist(): void {
    const sounds = this.sounds();
    if (!sounds.length) return;
    const name = prompt('Playlist name:')?.trim();
    if (!name) return;
    if (this.library.hasPlaylist(name) &&
        !confirm(`A playlist named “${name}” already exists. Overwrite it?`)) {
      return;
    }
    void this.library.savePlaylist(name, sounds);
  }
}
