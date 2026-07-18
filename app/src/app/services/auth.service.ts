import { Injectable, signal } from '@angular/core';

import { AuthState, fsc } from './fsc';
import { ToastService } from './toast.service';

@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly state = signal<AuthState>({ loggedIn: false, username: null, avatarUrl: null });
  readonly busy = signal(false);
  /** Emits once each time a login completes, so callers can resume work. */
  private loginResolvers: Array<(ok: boolean) => void> = [];

  constructor(private toast: ToastService) {
    const api = fsc();
    if (!api) return;
    api.auth.getState().then((s) => this.state.set(s));
    api.auth.onChanged((s) => this.state.set(s));
    api.auth.onLoginResult((result) => {
      this.busy.set(false);
      if (result.ok) {
        this.toast.info(`Logged in as ${this.state().username ?? 'you'}.`);
        this.resolveLogin(true);
      } else {
        this.toast.error(result.error ?? 'Login failed.');
        this.resolveLogin(false);
      }
    });
  }

  get isLoggedIn(): boolean {
    return this.state().loggedIn;
  }

  async ensureCredentials(): Promise<boolean> {
    const api = fsc();
    if (!api) return false;
    if (await api.auth.hasCredentials()) return true;
    this.toast.error(
      'This build is missing Freesound OAuth credentials. See the README ' +
      'for how to register a Freesound app.');
    return false;
  }

  /** Opens the browser flow; resolves when login succeeds or fails. */
  async login(): Promise<boolean> {
    const api = fsc();
    if (!api || !(await this.ensureCredentials())) return false;
    this.busy.set(true);
    this.toast.info('Opening your browser to log in to Freesound…');
    await api.auth.login();
    return new Promise<boolean>((resolve) => this.loginResolvers.push(resolve));
  }

  async submitCode(text: string): Promise<void> {
    const api = fsc();
    if (!api) return;
    this.busy.set(true);
    try {
      await api.auth.submitCode(text);
      this.busy.set(false);
      this.toast.info(`Logged in as ${this.state().username ?? 'you'}.`);
      this.resolveLogin(true);
    } catch (err: any) {
      this.busy.set(false);
      this.toast.error(String(err?.message ?? err));
    }
  }

  async cancelLogin(): Promise<void> {
    await fsc()?.auth.cancelLogin();
    this.busy.set(false);
    this.resolveLogin(false);
  }

  async logout(): Promise<void> {
    await fsc()?.auth.logout();
    this.toast.info('Logged out.');
  }

  private resolveLogin(ok: boolean): void {
    const resolvers = this.loginResolvers;
    this.loginResolvers = [];
    resolvers.forEach((r) => r(ok));
  }
}
