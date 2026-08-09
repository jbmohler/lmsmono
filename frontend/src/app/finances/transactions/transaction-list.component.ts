import { Component, afterNextRender, inject, signal, viewChild, ElementRef, computed, ChangeDetectionStrategy } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { BehaviorSubject, Subject, combineLatest, merge } from 'rxjs';
import { auditTime, debounceTime, startWith, switchMap } from 'rxjs/operators';
import { TransactionEntryComponent } from './transaction-entry/transaction-entry.component';
import { TransactionService } from '../services/transaction.service';
import { ChangeNotificationService } from '@core/events/change-notification.service';
import { TransactionFilters } from '@finances/models/transaction.model';
import { ColumnMeta } from '@core/api/api.types';

const SEARCH_DEBOUNCE_MS = 300;

/**
 * Collapses a local save and the notification it echoes back into one refetch,
 * and coalesces bursts of changes from other users.
 */
const REFRESH_COALESCE_MS = 150;

function defaultFromDate(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 3);
  return d.toISOString().slice(0, 10);
}

@Component({
  selector: 'app-transaction-list',
  templateUrl: './transaction-list.component.html',
  styleUrl: './transaction-list.component.scss',
  imports: [FormsModule, DatePipe, TransactionEntryComponent],
  changeDetection: ChangeDetectionStrategy.Eager,
  host: {
    '(window:keydown)': 'handleGlobalKeydown($event)',
  },
})
export class TransactionListComponent {
  private transactionService = inject(TransactionService);
  private changes = inject(ChangeNotificationService);

  searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');

  showEntryDialog = signal(false);
  editTransactionId = signal<string | undefined>(undefined);

  // Local filter state
  private filters$ = new BehaviorSubject<TransactionFilters>({ from: defaultFromDate() });
  private refresh$ = new Subject<void>();

  // Bind to template inputs
  searchQuery = '';
  dateFrom = defaultFromDate();
  dateTo = '';

  // Refetch on our own writes and on anyone else's, from any tab or user
  private trigger$ = merge(
    this.refresh$,
    this.changes.forEntity('transactions')
  ).pipe(auditTime(REFRESH_COALESCE_MS), startWith(undefined));

  // Local reactive data pipeline
  private listResponse = toSignal(
    combineLatest([
      this.filters$.pipe(debounceTime(SEARCH_DEBOUNCE_MS)),
      this.trigger$,
    ]).pipe(
      switchMap(([filters]) => this.transactionService.list(filters))
    )
  );

  transactions = computed(() => this.listResponse()?.data ?? []);
  columns = computed<ColumnMeta[]>(() => this.listResponse()?.columns ?? []);

  constructor() {
    afterNextRender(() => {
      this.searchInput()?.nativeElement?.focus();
    });
  }

  handleGlobalKeydown(event: KeyboardEvent): void {
    if (event.ctrlKey && event.shiftKey && event.key === 'N') {
      event.preventDefault();
      this.openEntryDialog();
    }
  }

  focusFilter(): void {
    this.searchInput()?.nativeElement?.focus();
  }

  onSearchChange(): void {
    this.setFilters({ q: this.searchQuery || undefined });
  }

  onDateFromChange(): void {
    this.setFilters({ from: this.dateFrom || undefined });
  }

  onDateToChange(): void {
    this.setFilters({ to: this.dateTo || undefined });
  }

  clearFilters(): void {
    this.searchQuery = '';
    this.dateFrom = defaultFromDate();
    this.dateTo = '';
    this.filters$.next({ from: defaultFromDate() });
  }

  openEntryDialog(transactionId?: string): void {
    this.editTransactionId.set(transactionId);
    this.showEntryDialog.set(true);
  }

  closeEntryDialog(): void {
    this.showEntryDialog.set(false);
    this.editTransactionId.set(undefined);
  }

  onTransactionSaved(): void {
    this.refresh$.next();
  }

  onRowClick(transactionId: string): void {
    this.openEntryDialog(transactionId);
  }

  private setFilters(filters: Partial<TransactionFilters>): void {
    this.filters$.next({ ...this.filters$.value, ...filters });
  }
}
