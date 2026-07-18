import {
  ChangeDetectionStrategy, Component, ElementRef, OnDestroy, computed,
  effect, viewChild,
} from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin, { Region as WsRegion } from 'wavesurfer.js/dist/plugins/regions.js';

import { Sound, fmtDuration } from '../models/sound';
import { DragService } from '../services/drag.service';
import { fsc } from '../services/fsc';
import { PlayerService } from '../services/player.service';
import { ToastService } from '../services/toast.service';

@Component({
  selector: 'app-player-bar',
  standalone: true,
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './player-bar.html',
  styleUrl: './player-bar.css',
})
export class PlayerBar implements OnDestroy {
  private readonly waveEl = viewChild.required<ElementRef<HTMLDivElement>>('wave');

  private ws?: WaveSurfer;
  private regions?: RegionsPlugin;
  private loadToken = -1;
  private blobUrl?: string;

  readonly current;
  readonly playing;
  readonly loading;
  readonly region;
  readonly timeLabel;
  readonly selectionLabel;

  constructor(
    readonly player: PlayerService,
    private toast: ToastService,
    private drag: DragService,
  ) {
    this.current = player.current;
    this.playing = player.playing;
    this.loading = player.loadingWaveform;
    this.region = player.region;
    this.timeLabel = computed(
      () => `${fmtDuration(player.positionSec())} / ${fmtDuration(player.durationSec())}`);
    this.selectionLabel = computed(() => {
      const r = player.region();
      if (!r) return null;
      return `Selection: ${fmtDuration(r.start)} – ${fmtDuration(r.end)}`;
    });

    // React to load requests coming from anywhere in the app.
    effect(() => {
      const req = this.player.loadRequest();
      if (req && req.token !== this.loadToken) {
        this.loadToken = req.token;
        void this.load(req.sound, req.autoplay);
      }
    });
    effect(() => {
      this.ws?.setVolume(this.player.volume());
    });
  }

  ngOnDestroy(): void {
    this.ws?.destroy();
    if (this.blobUrl) URL.revokeObjectURL(this.blobUrl);
  }

  private ensureWave(): WaveSurfer {
    if (this.ws) return this.ws;
    this.regions = RegionsPlugin.create();
    this.ws = WaveSurfer.create({
      container: this.waveEl().nativeElement,
      height: 68,
      waveColor: '#4f9dff',
      progressColor: '#35e0c3',
      cursorColor: '#ffffff',
      cursorWidth: 1,
      barWidth: 2,
      barGap: 2,
      barRadius: 2,
      normalize: true,
      // No dragToSeek: dragging is reserved for region selection below.
      // Clicking still seeks (wavesurfer's default `interact`).
      plugins: [this.regions],
    });
    this.ws.setVolume(this.player.volume());

    this.ws.on('play', () => this.player.playing.set(true));
    this.ws.on('pause', () => this.player.playing.set(false));
    this.ws.on('finish', () => this.player.playing.set(false));
    this.ws.on('timeupdate', (t) => {
      this.player.positionSec.set(t);
      const r = this.player.region();
      if (r && this.ws!.isPlaying() && t >= r.end - 0.01) {
        this.ws!.pause();
        this.ws!.setTime(r.start);
      }
    });
    this.ws.on('decode', (d) => this.player.durationSec.set(d));
    this.ws.on('ready', () => this.player.loadingWaveform.set(false));

    // Region interactions: enable drag-to-create, keep only one.
    this.regions.enableDragSelection({
      color: 'rgba(53, 224, 195, 0.18)',
    });
    this.regions.on('region-created', (region: WsRegion) => {
      this.regions!.getRegions()
        .filter((r) => r.id !== region.id)
        .forEach((r) => r.remove());
      this.setRegion(region);
    });
    this.regions.on('region-updated', (region: WsRegion) => this.setRegion(region));
    return this.ws;
  }

  private setRegion(region: WsRegion): void {
    this.player.region.set({ start: region.start, end: region.end });
  }

  private async load(sound: Sound, autoplay: boolean): Promise<void> {
    const api = fsc();
    if (!api) return;
    const ws = this.ensureWave();
    ws.stop();
    this.regions?.clearRegions();
    this.player.region.set(null);
    this.player.positionSec.set(0);
    this.player.durationSec.set(sound.duration || 0);
    this.player.loadingWaveform.set(true);
    const token = this.loadToken;
    try {
      const bytes = await api.sound.previewBytes(sound);
      if (token !== this.loadToken) return; // superseded
      const url = URL.createObjectURL(new Blob([bytes], { type: 'audio/mpeg' }));
      if (this.blobUrl) URL.revokeObjectURL(this.blobUrl);
      this.blobUrl = url;
      await ws.load(url);
      if (token !== this.loadToken) return;
      if (autoplay) void ws.play();
    } catch (err: any) {
      if (token === this.loadToken) {
        this.player.loadingWaveform.set(false);
        this.toast.error(`Could not load preview: ${err?.message ?? err}`);
      }
    }
  }

  togglePlay(): void {
    const ws = this.ws;
    if (!ws || !this.current()) return;
    if (ws.isPlaying()) {
      ws.pause();
      return;
    }
    const r = this.player.region();
    if (r) {
      const pos = ws.getCurrentTime();
      if (pos < r.start || pos >= r.end - 0.01) ws.setTime(r.start);
    }
    void ws.play();
  }

  stop(): void {
    this.ws?.stop();
  }

  clearSelection(): void {
    this.regions?.clearRegions();
    this.player.region.set(null);
  }

  onVolume(event: Event): void {
    const value = +(event.target as HTMLInputElement).value / 100;
    this.player.volume.set(value);
    this.ws?.setVolume(value); // apply immediately, don't wait on the effect
  }

  onDragToTimeline(event: DragEvent): void {
    const sound = this.current();
    if (sound) void this.drag.begin(event, sound);
  }
}
