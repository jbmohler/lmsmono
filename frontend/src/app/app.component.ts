import { Component, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterOutlet } from '@angular/router';

interface HealthResponse {
  status: string;
  config_loaded: boolean;
  database_host: string | null;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    <div class="min-h-screen flex items-center justify-center">
      <div class="bg-white p-8 rounded-lg shadow-lg max-w-md w-full">
        <h1 class="text-2xl font-bold text-gray-800 mb-4">LMS</h1>

        @if (health()) {
          <div class="space-y-2">
            <p class="text-sm">
              <span class="font-medium">Status:</span>
              <span class="ml-2 text-green-600">{{ health()?.status }}</span>
            </p>
            <p class="text-sm">
              <span class="font-medium">Config loaded:</span>
              <span class="ml-2">{{ health()?.config_loaded }}</span>
            </p>
            <p class="text-sm">
              <span class="font-medium">Database:</span>
              <span class="ml-2">{{ health()?.database_host }}</span>
            </p>
          </div>
        } @else if (error()) {
          <p class="text-red-600 text-sm">{{ error() }}</p>
        } @else {
          <p class="text-gray-500 text-sm">Loading...</p>
        }

        <button
          (click)="checkHealth()"
          class="mt-6 w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Check API Health
        </button>
      </div>
    </div>
    <router-outlet />
  `,
})
export class AppComponent {
  health = signal<HealthResponse | null>(null);
  error = signal<string | null>(null);

  constructor(private http: HttpClient) {}

  checkHealth(): void {
    this.error.set(null);
    this.http.get<HealthResponse>('/api/health').subscribe({
      next: (response) => this.health.set(response),
      error: (err) => this.error.set(`Failed to connect: ${err.message}`),
    });
  }
}
