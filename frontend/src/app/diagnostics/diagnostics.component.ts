import { Component, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { toSignal } from '@angular/core/rxjs-interop';
import { Subject, range, defer } from 'rxjs';
import { switchMap, startWith, concatMap, map, toArray } from 'rxjs/operators';

interface HealthResponse {
  status: string;
  config_loaded: boolean;
  database_host: string | null;
  database_connected: boolean;
  database_version: string | null;
}

interface PingStats {
  avg: number;
  max: number;
}

const PING_COUNT = 25;

@Component({
  selector: 'app-diagnostics',
  templateUrl: './diagnostics.component.html',
  styleUrl: './diagnostics.component.scss',
  imports: [],
})
export class DiagnosticsComponent {
  private http = inject(HttpClient);
  private refresh$ = new Subject<void>();

  health = toSignal(
    this.refresh$.pipe(
      startWith(undefined),
      switchMap(() => this.http.get<HealthResponse>('/api/health'))
    )
  );

  pingStats = toSignal<PingStats | null>(
    this.refresh$.pipe(
      startWith(undefined),
      switchMap(() =>
        range(PING_COUNT).pipe(
          concatMap(() =>
            defer(() => {
              const start = Date.now();
              return this.http.get('/api/ping').pipe(map(() => Date.now() - start));
            })
          ),
          toArray(),
          map(times => ({
            avg: Math.round(times.reduce((a, b) => a + b) / times.length),
            max: Math.max(...times),
          })),
          startWith(null)
        )
      )
    ),
    { initialValue: null }
  );

  refresh(): void {
    this.refresh$.next();
  }
}
