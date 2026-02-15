import { Component, afterNextRender, inject, signal, viewChild, ElementRef, computed } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { BehaviorSubject, Subject, combineLatest } from 'rxjs';
import { debounceTime, startWith, switchMap } from 'rxjs/operators';
import { TransactionEntryComponent } from './transaction-entry/transaction-entry.component';
import { TransactionService } from '../services/transaction.service';
import { TransactionFilters } from '@finances/models/transaction.model';
import { ColumnMeta } from '@core/api/api.types';

const SEARCH_DEBOUNCE_MS = 300;

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
  host: {
    '(window:keydown)': 'handleGlobalKeydown($event)',
  },
})
export class TransactionListComponent {
  private transactionService = inject(TransactionService);

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

  // Local reactive data pipeline
  private listResponse = toSignal(
    combineLatest([
      this.filters$.pipe(debounceTime(SEARCH_DEBOUNCE_MS)),
      this.refresh$.pipe(startWith(undefined)),
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
