import { Injectable } from '@angular/core';

import { encodeWavRegion } from '../audio/wav';
import { Sound } from '../models/sound';
import { RegionMs, fsc } from './fsc';
import { PlayerService } from './player.service';
import { ToastService } from './toast.service';

/**
 * Turns an HTML dragstart into a native OS file drag. The renderer must
 * call preventDefault() on the dragstart event (drags are started by the
 * main process via webContents.startDrag), so this returns immediately and
 * the actual file lands through IPC.
 */
@Injectable({ providedIn: 'root' })
export class DragService {
  constructor(private player: PlayerService, private toast: ToastService) {}

  async begin(event: DragEvent, sound: Sound): Promise<void> {
    event.preventDefault();
    const api = fsc();
    if (!api) return;

    // Export the trimmed region first if this sound is the active one and
    // has a selection — so the file is on disk before the drag starts.
    let region: RegionMs | null = null;
    if (this.player.current()?.id === sound.id) {
      region = this.player.regionMs();
      if (region) {
        const ready = await this.ensureRegion(sound, region);
        if (!ready) return;
      }
    }

    const result = await api.drag.start(sound, region);
    if (!result.ok && result.reason) {
      this.toast.info(result.reason);
    } else if (result.ok) {
      this.toast.info(
        `Drop “${sound.name}” on your Resolve timeline. Credit written to CREDITS.txt.`);
    }
  }

  private async ensureRegion(sound: Sound, region: RegionMs): Promise<boolean> {
    const api = fsc()!;
    if (await api.region.exists(sound, region.startMs, region.endMs)) return true;
    try {
      this.toast.setStatus(`Exporting selection of “${sound.name}”…`);
      // Prefer the original-quality bytes; fall back to the preview if the
      // original isn't cached or the browser can't decode its format.
      const bytes = await api.sound.originalBytes(sound)
        ?? await api.sound.previewBytes(sound);
      const buffer = await this.decode(bytes);
      const wav = encodeWavRegion(buffer, region.startMs / 1000, region.endMs / 1000);
      await api.region.save(sound, region.startMs, region.endMs, wav);
      return true;
    } catch (err: any) {
      this.toast.error(`Could not export selection: ${err?.message ?? err}`);
      return false;
    }
  }

  private async decode(bytes: ArrayBuffer): Promise<AudioBuffer> {
    const ctx = new OfflineAudioContext(1, 1, 44100);
    return ctx.decodeAudioData(bytes.slice(0));
  }
}
