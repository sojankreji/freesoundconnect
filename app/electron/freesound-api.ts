/** Freesound HTTP API client (main process only — no CORS, token stays here). */
import * as fs from "fs";
import * as path from "path";

export const API_BASE = "https://freesound.org/apiv2";
export const PAGE_SIZE = 30;
export const SEARCH_FIELDS =
  "id,name,previews,duration,username,license,url,type,samplerate," +
  "channels,bitdepth,filesize,num_downloads,avg_rating,num_ratings," +
  "tags,description,created";

const USER_AGENT = "FreesoundConnect/3.0.0";

export class FreesoundError extends Error {}

async function apiFetch(url: string, accessToken?: string): Promise<Response> {
  const headers: Record<string, string> = { "User-Agent": USER_AGENT };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  let resp: Response;
  try {
    resp = await fetch(url, { headers, signal: AbortSignal.timeout(30000) });
  } catch (err: any) {
    throw new FreesoundError(`Network error: ${err?.message ?? err}`);
  }
  if (resp.status === 401) {
    throw new FreesoundError(
      "Your Freesound login expired. Please log in again.");
  }
  if (!resp.ok) {
    throw new FreesoundError(`Freesound returned HTTP ${resp.status}.`);
  }
  return resp;
}

export interface SearchParams {
  query: string;
  page: number;
  sort: string;
  licenseFilter?: string | null;
  extraFilter?: string | null;
}

export async function searchSounds(
  accessToken: string, params: SearchParams): Promise<any> {
  const qs = new URLSearchParams({
    query: params.query,
    page: String(params.page),
    page_size: String(PAGE_SIZE),
    fields: SEARCH_FIELDS,
    sort: params.sort,
  });
  const filters: string[] = [];
  if (params.licenseFilter) filters.push(`license:${params.licenseFilter}`);
  if (params.extraFilter) filters.push(params.extraFilter);
  if (filters.length) qs.set("filter", filters.join(" "));
  const resp = await apiFetch(
    `${API_BASE}/search/text/?${qs.toString()}`, accessToken);
  return resp.json();
}

export async function fetchProfile(accessToken: string): Promise<{
  username: string | null; avatar_url: string | null;
}> {
  const me: any = await (await apiFetch(`${API_BASE}/me/`, accessToken)).json();
  const username: string | null = me.username ?? null;
  let avatarUrl: string | null = null;
  if (username) {
    try {
      const user: any = await (await apiFetch(
        `${API_BASE}/users/${encodeURIComponent(username)}/`)).json();
      const avatar = user.avatar ?? {};
      avatarUrl = avatar.medium ?? avatar.small ?? avatar.large ?? null;
    } catch {
      /* avatar is best-effort */
    }
  }
  return { username, avatar_url: avatarUrl };
}

export function previewUrl(sound: any): string {
  const previews = sound?.previews ?? {};
  const url = previews["preview-hq-mp3"] ?? previews["preview-lq-mp3"];
  if (!url) throw new FreesoundError("No preview available for this sound.");
  return url;
}

export function originalDownloadUrl(sound: any): string {
  return `${API_BASE}/sounds/${sound.id}/download/`;
}

export function sanitizeFilename(name: string): string {
  const cleaned = name.replace(/[^\w\s.-]/g, "").trim().replace(/\s+/g, "_");
  return cleaned.slice(0, 80) || "sound";
}

export function originalFilename(sound: any): string {
  const ext = sound.type || "wav";
  return `${sound.id}__${sanitizeFilename(sound.name)}.${ext}`;
}

/** Stream a URL to a file (atomically via .part), reporting progress 0..1. */
export async function downloadToFile(
  url: string, dest: string, accessToken?: string,
  onProgress?: (fraction: number) => void): Promise<string> {
  const resp = await apiFetch(url, accessToken);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  const tmp = dest + ".part";
  const total = Number(resp.headers.get("content-length") ?? 0);
  const out = fs.createWriteStream(tmp);
  let received = 0;
  try {
    const reader = resp.body!.getReader();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      received += value.byteLength;
      if (total && onProgress) onProgress(Math.min(1, received / total));
      await new Promise<void>((resolve, reject) => {
        out.write(Buffer.from(value), (err) => err ? reject(err) : resolve());
      });
    }
    await new Promise<void>((resolve, reject) => {
      out.end((err: unknown) => err ? reject(err) : resolve());
    });
    fs.renameSync(tmp, dest);
    return dest;
  } catch (err) {
    out.destroy();
    fs.rmSync(tmp, { force: true });
    throw err;
  }
}
