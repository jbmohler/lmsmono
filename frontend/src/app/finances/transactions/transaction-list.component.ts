import { Component, afterNextRender, inject, signal, viewChild, ElementRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { TransactionEntryComponent } from './transaction-entry/transaction-entry.component';
import { TransactionService } from '../services/transaction.service';

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

  // Bind to service filters
  searchQuery = '';
  dateFrom = '';
  dateTo = '';

  // Expose service data to template
  transactions = this.transactionService.transactions;
  columns = this.transactionService.columns;

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
    this.transactionService.setFilters({ q: this.searchQuery || undefined });
  }

  onDateFromChange(): void {
    this.transactionService.setFilters({ from: this.dateFrom || undefined });
  }

  onDateToChange(): void {
    this.transactionService.setFilters({ to: this.dateTo || undefined });
  }

  clearFilters(): void {
    this.searchQuery = '';
    this.dateFrom = '';
    this.dateTo = '';
    this.transactionService.clearFilters();
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
    this.transactionService.refresh();
  }

  onRowClick(transactionId: string): void {
    this.openEntryDialog(transactionId);
  }
}
