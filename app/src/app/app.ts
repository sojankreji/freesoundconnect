import {
  ChangeDetectionStrategy, Component, HostListener, effect, signal,
} from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

import { LoginDialog } from './components/login-dialog';
import { PlayerBar } from './player/player-bar';
import { ShotlistPopover } from './shotlist/shotlist-popover';
import { AuthService } from './services/auth.service';
import { LibraryService } from './services/library.service';
import { SearchService } from './services/search.service';
import { ToastService } from './services/toast.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterOutlet, RouterLink, RouterLinkActive, LucideAngularModule,
    PlayerBar, ShotlistPopover, LoginDialog,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  readonly cartOpen = signal(false);
  private trendingLoaded = false;

  constructor(
    readonly auth: AuthService,
    readonly library: LibraryService,
    readonly toast: ToastService,
    private search: SearchService,
  ) {
    // Auth state arrives asynchronously (IPC). Load trending as soon as we
    // know we're logged in; show the prompt otherwise.
    effect(() => {
      if (this.auth.isLoggedIn) {
        if (!this.trendingLoaded) {
          this.trendingLoaded = true;
          this.search.loadTrending();
        }
      } else if (!this.trendingLoaded) {
        this.toast.setStatus('Click “Log in with Freesound” to search and add sounds.');
      }
    });
  }

  toggleCart(): void {
    this.cartOpen.update((v) => !v);
  }

  async login(): Promise<void> {
    const ok = await this.auth.login();
    if (ok) this.search.loadTrending();
  }

  logout(): void {
    void this.auth.logout();
  }

  @HostListener('document:keydown', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && this.cartOpen()) this.cartOpen.set(false);
  }
}
