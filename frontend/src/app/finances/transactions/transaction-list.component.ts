import { Component, ElementRef, ViewChild, AfterViewInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TransactionEntryComponent } from './transaction-entry/transaction-entry.component';

@Component({
  selector: 'app-transaction-list',
  templateUrl: './transaction-list.component.html',
  styleUrl: './transaction-list.component.scss',
  imports: [FormsModule, TransactionEntryComponent],
  host: {
    '(window:keydown)': 'handleGlobalKeydown($event)',
  },
})
export class TransactionListComponent implements AfterViewInit {
  @ViewChild('searchInput') searchInput!: ElementRef<HTMLInputElement>;

  showEntryDialog = signal(false);

  searchQuery = '';
  dateFrom = '';
  dateTo = '';

  ngAfterViewInit(): void {
    // Focus the search input when navigating here via hotkey
    // The slight delay ensures the view is fully rendered
    setTimeout(() => {
      this.searchInput?.nativeElement?.focus();
    }, 0);
  }

  handleGlobalKeydown(event: KeyboardEvent): void {
    // Ctrl+Shift+N - open new transaction dialog (avoid Ctrl+N browser new-tab)
    if (event.ctrlKey && event.shiftKey && event.key === 'N') {
      event.preventDefault();
      this.openEntryDialog();
    }
  }

  focusFilter(): void {
    this.searchInput?.nativeElement?.focus();
  }

  openEntryDialog(): void {
    this.showEntryDialog.set(true);
  }

  closeEntryDialog(): void {
    this.showEntryDialog.set(false);
  }

  onTransactionSaved(): void {
    // TODO: Refresh transaction list when API is connected
    console.log('Transaction saved');
  }
}
