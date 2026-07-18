import { ChangeDetectionStrategy, Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { SoundList } from '../components/sound-list';
import { PlayerService } from '../services/player.service';
import {
  LICENSE_CHOICES, SORT_CHOICES, SearchService,
} from '../services/search.service';
import { fsc } from '../services/fsc';

@Component({
  selector: 'app-search-page',
  standalone: true,
  imports: [FormsModule, LucideAngularModule, SoundList],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './search-page.html',
  styleUrl: './search-page.css',
})
export class SearchPage {
  readonly licenses = LICENSE_CHOICES.map(([label]) => label);
  readonly sorts = SORT_CHOICES.map(([label]) => label);
  readonly skeletonRows = Array.from({ length: 8 });

  constructor(
    readonly search: SearchService,
    private player: PlayerService,
  ) {}

  openSelectedOnFreesound(): void {
    const sound = this.player.current();
    if (sound?.url) void fsc()?.app.openExternal(sound.url);
  }

  openDownloads(): void {
    void fsc()?.app.openDownloads();
  }
}
