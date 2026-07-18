import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withHashLocation } from '@angular/router';
import {
  AudioLines, Check, ChevronLeft, ChevronRight, ExternalLink, Folder,
  GripVertical, Heart, Info, Library, LucideAngularModule, ListPlus, Loader,
  Minus, Music, Pause, Pencil, Play, Plus, Search, Square, Trash2,
  TriangleAlert, User, Volume2, X,
} from 'lucide-angular';

import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withHashLocation()),
    LucideAngularModule.pick({
      AudioLines, Check, ChevronLeft, ChevronRight, ExternalLink, Folder,
      GripVertical, Heart, Info, Library, ListPlus, Loader, Minus, Music,
      Pause, Pencil, Play, Plus, Search, Square, Trash2, TriangleAlert, User,
      Volume2, X,
    }).providers!,
  ],
};
