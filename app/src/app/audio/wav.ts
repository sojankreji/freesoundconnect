/** Encode a slice of an AudioBuffer as a 16-bit PCM WAV file. */

export function encodeWavRegion(
  buffer: AudioBuffer, startSec: number, endSec: number): ArrayBuffer {
  const channels = buffer.numberOfChannels;
  const rate = buffer.sampleRate;
  const startFrame = Math.max(0, Math.min(buffer.length, Math.floor(startSec * rate)));
  const endFrame = Math.max(startFrame, Math.min(buffer.length, Math.floor(endSec * rate)));
  const frames = endFrame - startFrame;
  if (frames < 1) throw new Error('Selection is too short to export.');

  const dataSize = frames * channels * 2;
  const out = new ArrayBuffer(44 + dataSize);
  const view = new DataView(out);

  const writeString = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, channels, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * channels * 2, true);
  view.setUint16(32, channels * 2, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, dataSize, true);

  const channelData: Float32Array[] = [];
  for (let ch = 0; ch < channels; ch++) channelData.push(buffer.getChannelData(ch));

  let offset = 44;
  for (let frame = startFrame; frame < endFrame; frame++) {
    for (let ch = 0; ch < channels; ch++) {
      const sample = Math.max(-1, Math.min(1, channelData[ch][frame]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += 2;
    }
  }
  return out;
}
