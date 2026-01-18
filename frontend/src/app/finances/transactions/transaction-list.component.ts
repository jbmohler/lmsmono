import { Component, ElementRef, ViewChild, AfterViewInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-transaction-list',
  templateUrl: './transaction-list.component.html',
  styleUrl: './transaction-list.component.scss',
  imports: [FormsModule],
})
export class TransactionListComponent implements AfterViewInit {
  @ViewChild('searchInput') searchInput!: ElementRef<HTMLInputElement>;

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

  focusFilter(): void {
    this.searchInput?.nativeElement?.focus();
  }
}
