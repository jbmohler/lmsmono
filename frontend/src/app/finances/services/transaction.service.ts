import { Injectable, inject, computed } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { BehaviorSubject, Subject, combineLatest } from 'rxjs';
import { debounceTime, startWith, switchMap } from 'rxjs/operators';

import { ApiService } from '../../core/api/api.service';
import { ColumnMeta } from '../../core/api/api.types';
import {
  TemplateSearchResult,
  Transaction,
  TransactionCreate,
  TransactionDetail,
  TransactionFilters,
  TransactionUpdate,
} from '../models/transaction.model';

const SEARCH_DEBOUNCE_MS = 300;

/**
 * Service for transaction operations with reactive filtering.
 */
@Injectable({ providedIn: 'root' })
export class TransactionService {
  private api = inject(ApiService);

  // Filter state
  private filters$ = new BehaviorSubject<TransactionFilters>({});

  // Manual refresh trigger
  private refresh$ = new Subject<void>();

  // Combined stream: filters + refresh trigger, with debounce for search
  private listResponse = toSignal(
    combineLatest([
      this.filters$.pipe(debounceTime(SEARCH_DEBOUNCE_MS)),
      this.refresh$.pipe(startWith(undefined)),
    ]).pipe(
      switchMap(([filters]) =>
        this.api.getMany<Transaction>('/api/transactions', {
          q: filters.q,
          account_id: filters.account_id,
          from: filters.from,
          to: filters.to,
        })
      )
    )
  );

  /** Current transaction list */
  transactions = computed(() => this.listResponse()?.data ?? []);

  /** Column metadata for transactions */
  columns = computed<ColumnMeta[]>(() => this.listResponse()?.columns ?? []);

  /** Current filter values (readonly) */
  currentFilters = computed(() => this.filters$.value);

  /** Update filters (partial update) */
  setFilters(filters: Partial<TransactionFilters>): void {
    this.filters$.next({ ...this.filters$.value, ...filters });
  }

  /** Clear all filters */
  clearFilters(): void {
    this.filters$.next({});
  }

  /** Trigger a manual refresh of the transaction list */
  refresh(): void {
    this.refresh$.next();
  }

  /** Get a single transaction by ID with its splits */
  getById(id: string) {
    return this.api.getOne<TransactionDetail>(`/api/transactions/${id}`);
  }

  /** Create a new transaction with splits */
  create(data: TransactionCreate) {
    return this.api.create<TransactionDetail, TransactionCreate>('/api/transactions', data);
  }

  /** Update an existing transaction */
  update(id: string, data: TransactionUpdate) {
    return this.api.update<TransactionDetail, TransactionUpdate>(
      `/api/transactions/${id}`,
      data
    );
  }

  /** Delete a transaction */
  delete(id: string) {
    return this.api.delete(`/api/transactions/${id}`);
  }

  /** Search for a transaction template to auto-fill new transactions */
  searchTemplate(query: string) {
    return this.api.getOne<TemplateSearchResult | null>(
      `/api/transactions/template-search`,
      { q: query }
    );
  }
}
