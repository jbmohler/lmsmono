import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'diagnostics', pathMatch: 'full' },
  {
    path: 'diagnostics',
    loadComponent: () => import('./diagnostics/diagnostics.component').then(m => m.DiagnosticsComponent),
  },
];
