import { Injectable, signal } from '@angular/core';

import { Sound } from '../models/sound';
import { AuthService } from './auth.service';
import { SearchParams, fsc } from './fsc';
import { ToastService } from './toast.service';

export const LICENSE_CHOICES: Array<[string, string | null]> = [
  ['Any license', null],
  ['CC0 (public domain)', '"Creative Commons 0"'],
  ['CC-BY (attribution)', '"Attribution"'],
  ['CC-BY-NC (non-commercial)', '"Attribution Noncommercial"'],
];

export const SORT_CHOICES: Array<[string, string]> = [
  ['Relevance', 'score'],
  ['Most downloaded', 'downloads_desc'],
  ['Highest rated', 'rating_desc'],
  ['Newest', 'created_desc'],
  ['Shortest', 'duration_asc'],
  ['Longest', 'duration_desc'],
];

export const PAGE_SIZE = 30;
const TRENDING_FILTER = 'created:[NOW-90DAYS TO NOW]';
const TRENDING_LABEL = '🔥 Trending on Freesound — most downloaded of the last 3 months.';

interface SearchContext {
  query: string;
  sort?: string;
  extraFilter?: string;
  label?: string;
}

@Injectable({ providedIn: 'root' })
export class SearchService {
  readonly results = signal<Sound[]>([]);
  readonly loading = signal(false);
  readonly page = signal(1);
  readonly totalPages = signal(1);
  readonly banner = signal<string | null>(null);

  readonly licenseIndex = signal(0);
  readonly sortIndex = signal(0);
  readonly queryText = signal('');

  private ctx: SearchContext | null = null;
  private seq = 0;
  private pendingAfterLogin = false;

  constructor(private auth: AuthService, private toast: ToastService) {}

  /** Called on app start and after login, before any manual search. */
  loadTrending(): void {
    this.page.set(1);
    this.ctx = {
      query: '',
      sort: 'downloads_desc',
      extraFilter: TRENDING_FILTER,
      label: TRENDING_LABEL,
    };
    void this.run();
  }

  search(): void {
    const query = this.queryText().trim();
    if (!query) {
      this.toast.info('Type something to search for.');
      return;
    }
    this.page.set(1);
    this.ctx = { query };
    void this.run();
  }

  changePage(delta: number): void {
    const next = this.page() + delta;
    if (!this.ctx || next < 1 || next > this.totalPages()) return;
    this.page.set(next);
    void this.run();
  }

  private async run(): Promise<void> {
    if (!this.auth.isLoggedIn) {
      this.pendingAfterLogin = true;
      const ok = await this.auth.login();
      if (!ok) {
        this.pendingAfterLogin = false;
        return;
      }
      this.pendingAfterLogin = false;
    }
    const ctx = this.ctx;
    const api = fsc();
    if (!ctx || !api) return;

    const seq = ++this.seq;
    this.loading.set(true);
    this.toast.setStatus(ctx.label ? 'Loading trending sounds…' : `Searching for “${ctx.query}”…`);

    const params: SearchParams = {
      query: ctx.query,
      page: this.page(),
      sort: ctx.sort ?? SORT_CHOICES[this.sortIndex()][1],
      licenseFilter: LICENSE_CHOICES[this.licenseIndex()][1],
      extraFilter: ctx.extraFilter ?? null,
    };

    try {
      const data = await api.search.run(params);
      if (seq !== this.seq) return; // superseded
      const count = data.count ?? 0;
      this.totalPages.set(Math.max(1, Math.ceil(count / PAGE_SIZE)));
      this.results.set(data.results ?? []);
      this.banner.set(ctx.label ?? null);
      this.toast.setStatus(ctx.label ?? `${count} sounds found.`);
    } catch (err: any) {
      if (seq === this.seq) this.toast.error(String(err?.message ?? err));
    } finally {
      if (seq === this.seq) this.loading.set(false);
    }
  }
}
