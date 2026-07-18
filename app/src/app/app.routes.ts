import { Routes } from '@angular/router';

import { PlaylistsPage } from './pages/playlists-page';
import { SearchPage } from './pages/search-page';

export const routes: Routes = [
  { path: 'search', component: SearchPage },
  { path: 'playlists', component: PlaylistsPage },
  { path: '', pathMatch: 'full', redirectTo: 'search' },
];
