import {
  Component,
  signal,
  viewChild,
  ElementRef,
  afterNextRender,
  inject,
  effect,
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

  constructor() {
    afterNextRender(() => {
      this.searchInput()?.nativeElement.focus();
    });

    effect(() => {
      this.contactsService.search.set(this.searchQuery());
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

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      const isOtherInputFocused =
        !isSearchFocused &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT');

      if (!isOtherInputFocused) {
        event.preventDefault();
        this.navigateList(event.key === 'ArrowDown' ? 1 : -1);
      }
    }

    if (event.key === 'Enter' && isSearchFocused) {
      event.preventDefault();
      const list = this.filteredContacts();
      if (list.length > 0 && !this.selectedContactId()) {
        this.selectContact(list[0]);
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
