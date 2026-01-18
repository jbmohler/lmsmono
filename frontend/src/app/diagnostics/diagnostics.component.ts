import { Component, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { Subject } from 'rxjs';
import { switchMap, startWith } from 'rxjs/operators';

interface HealthResponse {
  status: string;
  config_loaded: boolean;
  database_host: string | null;
  database_connected: boolean;
}

interface EventLogEntry {
  id: number;
  logtype: string;
  logtime: string;
  descr: string | null;
}

@Component({
  selector: 'app-diagnostics',
  templateUrl: './diagnostics.component.html',
  styleUrl: './diagnostics.component.scss',
  imports: [FormsModule, DatePipe],
})
export class DiagnosticsComponent {
  private http = inject(HttpClient);

  // Health status with refresh trigger
  private refreshHealth$ = new Subject<void>();
  health = toSignal(
    this.refreshHealth$.pipe(
      startWith(undefined),
      switchMap(() => this.http.get<HealthResponse>('/api/health'))
    )
  );

  // Event log with refresh trigger
  private refreshEventLog$ = new Subject<void>();
  eventLog = toSignal(
    this.refreshEventLog$.pipe(
      startWith(undefined),
      switchMap(() => this.http.get<EventLogEntry[]>('/api/eventlog'))
    )
  );

  // Form state
  newLogType = '';
  newDescr = '';

  refreshHealth(): void {
    this.refreshHealth$.next();
  }

  refreshEventLog(): void {
    this.refreshEventLog$.next();
  }

  addEntry(): void {
    if (!this.newLogType) return;

    this.http.post<EventLogEntry>('/api/eventlog', {
      logtype: this.newLogType,
      descr: this.newDescr || null
    }).subscribe({
      next: () => {
        this.newLogType = '';
        this.newDescr = '';
        this.refreshEventLog();
      },
      error: (err) => console.error('Failed to add entry:', err),
    });
  }
}
