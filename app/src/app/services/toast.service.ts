import { Injectable, signal } from '@angular/core';

export interface Toast {
  id: number;
  text: string;
  kind: 'info' | 'error';
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly toasts = signal<Toast[]>([]);
  /** Persistent one-line status (mirrors the old Qt status bar). */
  readonly status = signal('Ready.');
  private nextId = 1;

  info(text: string): void {
    this.status.set(text);
    this.push(text, 'info');
  }

  error(text: string): void {
    this.status.set(text);
    this.push(text, 'error');
  }

  /** Quiet status update with no toast (e.g. background progress). */
  setStatus(text: string): void {
    this.status.set(text);
  }

  private push(text: string, kind: Toast['kind']): void {
    const id = this.nextId++;
    this.toasts.update((list) => [...list, { id, text, kind }]);
    setTimeout(() => this.dismiss(id), kind === 'error' ? 6000 : 3500);
  }

  dismiss(id: number): void {
    this.toasts.update((list) => list.filter((t) => t.id !== id));
  }
}
