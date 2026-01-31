import { Injectable, inject, computed } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Subject } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';

import { ApiService } from '@core/api/api.service';
import { ColumnMeta } from '@core/api/api.types';
import { AccountType } from '@finances/models/account.model';

/**
 * Service for account type operations.
 */
@Injectable({ providedIn: 'root' })
export class AccountTypeService {
  private api = inject(ApiService);

  private refresh$ = new Subject<void>();

  private listResponse = toSignal(
    this.refresh$.pipe(
      startWith(undefined),
      switchMap(() => this.api.getMany<AccountType>('/api/account-types'))
    )
  );

  /** All account types */
  accountTypes = computed(() => this.listResponse()?.data ?? []);

  /** Column metadata */
  columns = computed<ColumnMeta[]>(() => this.listResponse()?.columns ?? []);

  /** Trigger a refresh */
  refresh(): void {
    this.refresh$.next();
  }
}
