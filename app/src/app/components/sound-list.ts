import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';

import {
  Sound, fmtDuration, fmtRating, fmtSpecs, shortLicense, soundTooltip,
} from '../models/sound';
import { DragService } from '../services/drag.service';
import { LibraryService } from '../services/library.service';
import { PlayerService } from '../services/player.service';

/** Which optional columns to show — search wants everything, popovers less. */
export type ListVariant = 'full' | 'compact';

@Component({
  selector: 'app-sound-list',
  standalone: true,
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './sound-list.html',
  styleUrl: './sound-list.css',
})
export class SoundList {
  readonly sounds = input.required<Sound[]>();
  readonly variant = input<ListVariant>('full');
  readonly emptyText = input('No sounds.');
  readonly activate = output<Sound>();

  readonly full = computed(() => this.variant() === 'full');

  readonly fmtDuration = fmtDuration;
  readonly fmtSpecs = fmtSpecs;
  readonly fmtRating = fmtRating;
  readonly shortLicense = shortLicense;
  readonly tooltip = soundTooltip;

  constructor(
    private player: PlayerService,
    private drag: DragService,
    private library: LibraryService,
  ) {}

  isFavourite(sound: Sound): boolean {
    return this.library.inShotlist(sound.id);
  }

  toggleFavourite(event: Event, sound: Sound): void {
    event.stopPropagation();
    if (this.library.inShotlist(sound.id)) {
      void this.library.removeShot(sound.id);
    } else {
      void this.library.addShot(sound);
    }
  }

  isCurrent(sound: Sound): boolean {
    return this.player.current()?.id === sound.id;
  }

  isPlaying(sound: Sound): boolean {
    return this.isCurrent(sound) && this.player.playing();
  }

  onRowClick(sound: Sound): void {
    this.player.select(sound);
  }

  onRowDouble(sound: Sound): void {
    this.player.play(sound);
    this.activate.emit(sound);
  }

  onPlayClick(event: Event, sound: Sound): void {
    event.stopPropagation();
    this.player.play(sound);
  }

  onDragStart(event: DragEvent, sound: Sound): void {
    void this.drag.begin(event, sound);
  }

  /** Readiness dot state for the drag affordance. */
  readyState(sound: Sound): 'ready' | 'downloading' | 'idle' | 'error' {
    return this.player.downloadState(sound.id).phase === 'idle'
      ? 'idle'
      : this.player.downloadState(sound.id).phase;
  }

  progressPct(sound: Sound): number {
    return Math.round(this.player.downloadState(sound.id).progress * 100);
  }
}
