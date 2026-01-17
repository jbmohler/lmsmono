import { Component } from '@angular/core';
import { RouterOutlet, RouterLink } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
  template: `
    <div class="min-h-screen flex flex-col">
      <!-- Header -->
      <header class="bg-white shadow-sm">
        <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 class="text-xl font-bold text-gray-800">LMS</h1>
          <nav class="flex gap-4">
            <a routerLink="/diagnostics" class="text-gray-600 hover:text-gray-900">Diagnostics</a>
          </nav>
        </div>
      </header>

      <!-- Main Content -->
      <main class="flex-1 max-w-7xl mx-auto w-full px-4 py-8">
        <router-outlet />
      </main>
    </div>
  `,
})
export class AppComponent {}
