import { Component, ElementRef, ViewChild, AfterViewInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-contacts',
  templateUrl: './contacts.component.html',
  styleUrl: './contacts.component.scss',
  imports: [FormsModule],
})
export class ContactsComponent implements AfterViewInit {
  @ViewChild('searchInput') searchInput!: ElementRef<HTMLInputElement>;

  searchQuery = '';

  ngAfterViewInit(): void {
    // Focus the search input when navigating here via hotkey
    setTimeout(() => {
      this.searchInput?.nativeElement?.focus();
    }, 0);
  }

  focusFilter(): void {
    this.searchInput?.nativeElement?.focus();
  }
}
