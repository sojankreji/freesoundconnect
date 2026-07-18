/** Freesound sound object (subset of SEARCH_FIELDS) + display helpers. */

export interface Sound {
  id: number;
  name: string;
  duration: number;
  username: string;
  license: string;
  url: string;
  type: string;
  previews: Record<string, string>;
  samplerate?: number;
  channels?: number;
  bitdepth?: number;
  filesize?: number;
  num_downloads?: number;
  avg_rating?: number;
  num_ratings?: number;
  tags?: string[];
  description?: string;
  created?: string;
}

export function fmtDuration(seconds: number): string {
  const total = Math.max(0, Number(seconds) || 0);
  const mins = Math.floor(total / 60);
  const secs = total - mins * 60;
  return `${mins}:${secs.toFixed(2).padStart(5, '0')}`;
}

export function fmtSpecs(sound: Sound): string {
  const parts: string[] = [];
  if (sound.samplerate) parts.push(`${+(sound.samplerate / 1000).toFixed(1)} kHz`);
  if (sound.channels) {
    parts.push(sound.channels === 1 ? 'mono' : sound.channels === 2 ? 'stereo' : `${sound.channels}ch`);
  }
  if (sound.bitdepth) parts.push(`${sound.bitdepth}-bit`);
  return parts.join(' · ');
}

export function fmtRating(sound: Sound): string {
  if (!sound.num_ratings) return '—';
  return `★ ${(sound.avg_rating ?? 0).toFixed(1)} (${sound.num_ratings})`;
}

export function fmtFilesize(bytes?: number): string {
  if (!bytes) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  for (const unit of units) {
    if (value < 1024 || unit === 'GB') {
      return unit === 'B' ? `${value} B` : `${value.toFixed(1)} ${unit}`;
    }
    value /= 1024;
  }
  return '';
}

export function shortLicense(url: string): string {
  return (url || '')
    .replace(/https?:\/\/creativecommons\.org\/licenses\//, 'CC ')
    .replace(/https?:\/\/creativecommons\.org\/publicdomain\/zero\/1\.0\/?/, 'CC0');
}

export function soundTooltip(sound: Sound): string {
  const lines = [sound.name];
  const desc = (sound.description ?? '').trim();
  if (desc) lines.push('', desc.length > 400 ? desc.slice(0, 400) + '…' : desc);
  if (sound.tags?.length) lines.push('', 'Tags: ' + sound.tags.slice(0, 15).join(', '));
  const meta = [fmtFilesize(sound.filesize), sound.created ? 'uploaded ' + sound.created.slice(0, 10) : '']
    .filter(Boolean);
  if (meta.length) lines.push('', meta.join(' · '));
  return lines.join('\n');
}
