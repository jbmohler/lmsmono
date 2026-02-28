import { Component, computed, effect, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { Subject, combineLatest, of } from 'rxjs';
import { distinctUntilChanged, map, startWith, switchMap } from 'rxjs/operators';
import { CurrencyPipe, DatePipe } from '@angular/common';

import { ReconcileData, ReconcileSplit, FinalizeResult, ToggleResult } from '@finances/models/reconcile.model';

type FilterMode = 'all' | 'uncleared' | 'pending';

@Component({
  selector: 'app-reconcile',
  templateUrl: './reconcile.component.html',
  styleUrl: './reconcile.component.scss',
  imports: [CurrencyPipe, DatePipe],
})
export class ReconcileComponent {
  private route = inject(ActivatedRoute);
  private http = inject(HttpClient);

  accountId = toSignal(
    this.route.paramMap.pipe(map(params => params.get('accountId') ?? ''))
  );

  private refresh$ = new Subject<void>();

  reconcileData = toSignal(
    combineLatest([
      this.route.paramMap.pipe(
        map(params => params.get('accountId') ?? ''),
        distinctUntilChanged(),
      ),
      this.refresh$.pipe(startWith(undefined)),
    ]).pipe(
      switchMap(([accountId]) => {
        if (!accountId) return of(null);
        return this.http.get<ReconcileData>(`/api/reconcile/${accountId}`);
      })
    )
  );

  // Optimistic overrides: split_id → is_pending
  // Cleared when account changes or after finalize
  pendingOverrides = signal<Record<string, boolean>>({});

  // Statement inputs (UI-only, not persisted)
  statementDate = signal<string>('');
  statementBalanceStr = signal<string>('');

  // Filter
  filterMode = signal<FilterMode>('all');

  // Reset local state when account changes
  constructor() {
    effect(() => {
      this.accountId();
      this.pendingOverrides.set({});
      this.statementDate.set('');
      this.statementBalanceStr.set('');
      this.filterMode.set('all');
    }, { allowSignalWrites: true });
  }

  // Splits with optimistic overrides applied
  splits = computed<ReconcileSplit[]>(() => {
    const data = this.reconcileData();
    if (!data) return [];
    const overrides = this.pendingOverrides();
    return data.splits.map(s => ({
      ...s,
      is_pending: s.split_id in overrides ? overrides[s.split_id] : s.is_pending,
    }));
  });

  // Summary
  priorBalance = computed(() => this.reconcileData()?.prior_reconciled_balance ?? 0);

  clearedBalance = computed(() => {
    const prior = this.priorBalance();
    // Reconstruct raw sum: positive sum = debit, negative sum = -credit
    const pendingSum = this.splits()
      .filter(s => s.is_pending)
      .reduce((total, s) => total + (s.debit ?? -(s.credit ?? 0)), 0);
    return prior + pendingSum;
  });

  statementBalance = computed<number | null>(() => {
    const v = parseFloat(this.statementBalanceStr());
    return isNaN(v) ? null : v;
  });

  difference = computed<number | null>(() => {
    const sb = this.statementBalance();
    if (sb === null) return null;
    return this.clearedBalance() - sb;
  });

  isDifferenceZero = computed(() => {
    const d = this.difference();
    return d !== null && Math.abs(d) < 0.005;
  });

  // Counts
  pendingCount = computed(() => this.splits().filter(s => s.is_pending).length);
  unclearedCount = computed(() => this.splits().filter(s => !s.is_pending).length);

  canFinalize = computed(() => this.isDifferenceZero() && this.pendingCount() > 0);

  // Account info
  accName = computed(() => this.reconcileData()?.acc_name ?? '');
  recNote = computed(() => this.reconcileData()?.rec_note ?? null);

  // Filtered splits for display
  filteredSplits = computed(() => {
    const mode = this.filterMode();
    return this.splits().filter(s => {
      if (mode === 'uncleared') return !s.is_pending;
      if (mode === 'pending') return s.is_pending;
      return true;
    });
  });

  setFilter(mode: FilterMode): void {
    this.filterMode.set(mode);
  }

  toggle(splitId: string): void {
    const split = this.splits().find(s => s.split_id === splitId);
    if (!split) return;

    const newPending = !split.is_pending;

    // Optimistic update
    this.pendingOverrides.update(overrides => ({ ...overrides, [splitId]: newPending }));

    const accountId = this.accountId();
    if (!accountId) return;

    this.http
      .post<ToggleResult>(`/api/reconcile/${accountId}/splits/${splitId}/toggle`, {})
      .subscribe({
        error: () => {
          // Rollback on error
          this.pendingOverrides.update(overrides => ({
            ...overrides,
            [splitId]: split.is_pending,
          }));
        },
      });
  }

  finalize(): void {
    const accountId = this.accountId();
    if (!accountId) return;

    this.http
      .post<FinalizeResult>(`/api/reconcile/${accountId}/finalize`, {})
      .subscribe({
        next: () => {
          this.pendingOverrides.set({});
          this.statementBalanceStr.set('');
          this.statementDate.set('');
          this.filterMode.set('all');
          this.refresh$.next();
        },
      });
  }
}
