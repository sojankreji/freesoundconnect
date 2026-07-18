import { Injectable, computed, signal } from '@angular/core';

import { Sound } from '../models/sound';
import { DownloadState, RegionMs, fsc } from './fsc';
import { ToastService } from './toast.service';

/** Selected waveform region, in seconds. */
export interface Region {
  start: number;
  end: number;
}

/**
 * Central playback + file-readiness state. The <app-player-bar> component
 * owns the wavesurfer instance and calls back into here; everything else
 * (search rows, shotlist, playlists, drag) reads these signals.
 */
@Injectable({ providedIn: 'root' })
export class PlayerService {
  readonly current = signal<Sound | null>(null);
  readonly playing = signal(false);
  readonly positionSec = signal(0);
  readonly durationSec = signal(0);
  readonly volume = signal(0.8);
  readonly region = signal<Region | null>(null);
  readonly loadingWaveform = signal(false);
  /** Per-sound original-download readiness, mirrored from main. */
  readonly downloads = signal<Record<number, DownloadState>>({});

  readonly regionMs = computed<RegionMs | null>(() => {
    const r = this.region();
    if (!r || r.end - r.start < 0.05) return null;
    return { startMs: Math.round(r.start * 1000), endMs: Math.round(r.end * 1000) };
  });

  /** Set by the player-bar component so services can drive playback. */
  loadRequest = signal<{ sound: Sound; autoplay: boolean; token: number } | null>(null);
  private token = 0;

  constructor(private toast: ToastService) {
    const api = fsc();
    if (!api) return;
    api.sound.onDownloadState((state) => {
      this.downloads.update((map) => ({ ...map, [state.soundId]: state }));
    });
  }

  downloadState(soundId: number): DownloadState {
    return this.downloads()[soundId] ?? { soundId, phase: 'idle', progress: 0 };
  }

  /** Load a sound into the player and start background-fetching the original. */
  select(sound: Sound, autoplay = false): void {
    this.current.set(sound);
    this.region.set(null);
    this.loadRequest.set({ sound, autoplay, token: ++this.token });
    fsc()?.sound.prefetchOriginal(sound).then((state) => {
      this.downloads.update((map) => ({ ...map, [sound.id]: state }));
    });
  }

  play(sound: Sound): void {
    if (this.current()?.id === sound.id) {
      this.loadRequest.set({ sound, autoplay: true, token: ++this.token });
    } else {
      this.select(sound, true);
    }
  }
}
