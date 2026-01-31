import { Injectable, inject, computed } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Subject } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';

import { ApiService } from '@core/api/api.service';
import { ColumnMeta } from '@core/api/api.types';
import { Journal, JournalCreate, JournalUpdate } from '@finances/models/journal.model';

/**
 * Service for journal CRUD operations with reactive state.
 */
@Injectable({ providedIn: 'root' })
export class JournalService {
  private api = inject(ApiService);

  private refresh$ = new Subject<void>();

  private listResponse = toSignal(
    this.refresh$.pipe(
      startWith(undefined),
      switchMap(() => this.api.getMany<Journal>('/api/journals'))
    )
  );

  /** All journals */
  journals = computed(() => this.listResponse()?.data ?? []);

  /** Column metadata for journals */
  columns = computed<ColumnMeta[]>(() => this.listResponse()?.columns ?? []);

  /** Trigger a refresh of the journal list */
  refresh(): void {
    this.refresh$.next();
  }

  /** Get a single journal by ID */
  getById(id: string) {
    return this.api.getOne<Journal>(`/api/journals/${id}`);
  }

  /** Create a new journal */
  create(data: JournalCreate) {
    return this.api.create<Journal, JournalCreate>('/api/journals', data);
  }

  /** Update an existing journal */
  update(id: string, data: JournalUpdate) {
    return this.api.update<Journal, JournalUpdate>(`/api/journals/${id}`, data);
  }

  /** Delete a journal */
  delete(id: string) {
    return this.api.delete(`/api/journals/${id}`);
  }
}
