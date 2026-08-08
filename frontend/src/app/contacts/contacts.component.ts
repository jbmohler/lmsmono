import {
  Component,
  signal,
  viewChild,
  ElementRef,
  afterNextRender,
  inject,
  effect,
  ChangeDetectionStrategy
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { ContactDetailComponent } from './contact-detail/contact-detail.component';
import { ContactViewComponent } from './contact-view/contact-view.component';
import { ContactsService } from './services/contacts.service';
import { Persona, PersonaListItem } from './contacts.model';

@Component({
  selector: 'app-contacts',
  templateUrl: './contacts.component.html',
  styleUrl: './contacts.component.scss',
  imports: [FormsModule, ContactDetailComponent, ContactViewComponent],
  changeDetection: ChangeDetectionStrategy.Eager,
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class ContactsComponent {
  private contactsService = inject(ContactsService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');

  searchQuery = signal('');
  selectedContactId = signal<string | null>(null);
  mobileShowDetail = signal(false);

  // Only populated when creating a new contact (no ID yet)
  newContact = signal<Persona | null>(null);

  loading = this.contactsService.loading;
  error = this.contactsService.error;

  /** Term behind the current results; empty until a search has been run. */
  appliedSearch = this.contactsService.appliedSearch;

  /** Whether the current list came from a request at all. */
  listLoaded = this.contactsService.listLoaded;

  /** Last search term the detail pane was reconciled against. */
  private lastReconciledSearch: string | null = null;

  constructor() {
    afterNextRender(() => {
      this.searchInput()?.nativeElement.focus();
    });

    effect(() => {
      this.contactsService.search.set(this.searchQuery());
    });

    // Keep the detail pane consistent with the search results: if the open
    // contact is not among them, fall back to the first match (or nothing).
    effect(() => {
      const list = this.filteredContacts();
      const term = this.appliedSearch();

      // No search run yet (or the request failed) - the empty list is not a
      // statement about the open contact, so leave the selection alone.
      if (!term) {
        this.lastReconciledSearch = null;
        return;
      }
      // Only reconcile when the search itself changed. A plain list refresh
      // (after a save) must not kick the user off the record they just edited.
      if (term === this.lastReconciledSearch) return;
      this.lastReconciledSearch = term;

      const id = this.selectedContactId();
      if (!id) return;
      if (list.some(c => c.id === id)) return;

      const next = list.length > 0 ? list[0] : null;
      this.selectedContactId.set(next?.id ?? null);
      // Don't force the mobile detail pane open just because results changed.
      if (!next) this.mobileShowDetail.set(false);
      void this.router.navigate([], {
        queryParams: next ? { id: next.id } : {},
        replaceUrl: true,
      });
    });

    // Read ?id= from URL on load
    const initialId = this.route.snapshot.queryParamMap.get('id');
    if (initialId) {
      this.selectedContactId.set(initialId);
      this.mobileShowDetail.set(true);
    }
  }

  contacts = this.contactsService.contactsList;
  filteredContacts = this.contactsService.contactsList;

  handleKeydown(event: KeyboardEvent): void {
    if (event.ctrlKey && event.shiftKey && event.key === 'N') {
      event.preventDefault();
      this.createNewContact();
      return;
    }

    const target = event.target as HTMLElement;
    const isSearchFocused = target === this.searchInput()?.nativeElement;
    const isInInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable;

    if (event.key === 's' && !event.ctrlKey && !event.altKey && !event.metaKey && !isInInput) {
      event.preventDefault();
      this.searchInput()?.nativeElement.focus();
      return;
    }

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (!isInInput || isSearchFocused) {
        event.preventDefault();
        this.navigateList(event.key === 'ArrowDown' ? 1 : -1);
      }
    }

    if (event.key === 'Enter' && isSearchFocused && !this.searchQuery().trim()) {
      // Enter on an empty search box explicitly lists everything (up to the
      // API's page cap) instead of leaving the search-first empty state.
      event.preventDefault();
      this.contactsService.listAll();
      return;
    }

    if (event.key === 'Enter' && isSearchFocused) {
      event.preventDefault();
      const list = this.filteredContacts();
      if (list.length > 0 && !this.selectedContactId()) {
        this.selectContact(list[0]);
        // Enter is an explicit "open this one", so hand focus to the detail
        // pane — it only takes focus when the user is not typing in a field.
        this.searchInput()?.nativeElement.blur();
      }
    }
  }

  navigateList(direction: number): void {
    const list = this.filteredContacts();
    if (list.length === 0) return;

    const currentId = this.selectedContactId();
    const currentIndex = currentId ? list.findIndex(c => c.id === currentId) : -1;
    let newIndex = currentIndex + direction;

    if (newIndex < 0) newIndex = list.length - 1;
    if (newIndex >= list.length) newIndex = 0;

    this.selectContact(list[newIndex]);
  }

  selectContact(contact: PersonaListItem): void {
    this.newContact.set(null);
    this.selectedContactId.set(contact.id);
    this.mobileShowDetail.set(true);
    void this.router.navigate([], { queryParams: { id: contact.id }, replaceUrl: true });
  }

  createNewContact(): void {
    this.selectedContactId.set(null);
    this.newContact.set({
      id: '',
      firstName: '',
      lastName: '',
      title: '',
      organization: '',
      memo: '',
      birthday: null,
      anniversary: null,
      isCorporate: false,
      bits: [],
      tags: [],
    });
    this.mobileShowDetail.set(true);
    void this.router.navigate([], { queryParams: {}, replaceUrl: true });
  }

  async onNewContactSaved(contact: Persona): Promise<void> {
    try {
      const saved = await this.contactsService.create(contact);
      this.newContact.set(null);
      this.selectedContactId.set(saved.id);
      void this.router.navigate([], { queryParams: { id: saved.id }, replaceUrl: true });
    } catch {
      // error handled by service
    }
  }

  /** The open contact was deleted — clear the pane and the ?id= param. */
  onContactDeleted(): void {
    this.selectedContactId.set(null);
    this.mobileShowDetail.set(false);
    void this.router.navigate([], { queryParams: {}, replaceUrl: true });
  }

  // Display helpers
  getDisplayName(contact: PersonaListItem): string {
    return contact.entityName;
  }

  getSubtitle(contact: PersonaListItem): string {
    if (contact.isCorporate) return 'Company';
    return contact.organization || '';
  }

  trackById(_index: number, contact: PersonaListItem): string {
    return contact.id;
  }
}
