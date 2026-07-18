import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { AuthService } from '../services/auth.service';

/**
 * Modal shown while the browser OAuth flow is running. Mirrors the Qt
 * dialog's manual code-paste fallback for when the loopback redirect can't
 * reach 127.0.0.1 (strict firewall/proxy).
 */
@Component({
  selector: 'app-login-dialog',
  standalone: true,
  imports: [FormsModule, LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login-dialog.html',
  styleUrl: './login-dialog.css',
})
export class LoginDialog {
  readonly code = signal('');

  constructor(readonly auth: AuthService) {}

  submit(): void {
    const text = this.code().trim();
    if (text) void this.auth.submitCode(text);
  }

  cancel(): void {
    void this.auth.cancelLogin();
  }
}
