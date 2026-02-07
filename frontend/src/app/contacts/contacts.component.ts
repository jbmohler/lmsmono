import {
  Component,
  signal,
  computed,
  viewChild,
  ElementRef,
  afterNextRender,
  inject,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ContactDetailComponent } from './contact-detail/contact-detail.component';
import { ContactsService } from './services/contacts.service';
import { ContactBit, Persona, PersonaListItem } from './contacts.model';

@Component({
  selector: 'app-contacts',
  templateUrl: './contacts.component.html',
  styleUrl: './contacts.component.scss',
  imports: [FormsModule, ContactDetailComponent],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class ContactsComponent {
  private contactsService = inject(ContactsService);

  searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');

  searchQuery = signal('');
  selectedContactId = signal<string | null>(null);
  mobileShowDetail = signal(false);

  // Full contact data for the selected contact (loaded on demand)
  selectedContact = signal<Persona | null>(null);

  // Loading and error state from service
  loading = this.contactsService.loading;
  error = this.contactsService.error;

  constructor() {
    afterNextRender(() => {
      this.searchInput()?.nativeElement.focus();
    });
  }

  // Contact list from service
  contacts = this.contactsService.contactsList;

  // Client-side filtering on list data
  filteredContacts = computed(() => {
    const query = this.searchQuery().toLowerCase();
    const list = this.contacts();

    if (!query) return list;

    return list.filter(c => {
      const name = c.entityName.toLowerCase();
      const org = c.organization.toLowerCase();
      const email = c.primaryEmail.toLowerCase();
      return name.includes(query) || org.includes(query) || email.includes(query);
    });
  });

  handleKeydown(event: KeyboardEvent): void {
    // Ctrl+Shift+N - new contact
    if (event.ctrlKey && event.shiftKey && event.key === 'N') {
      event.preventDefault();
      this.createNewContact();
      return;
    }

    const target = event.target as HTMLElement;
    const isSearchFocused = target === this.searchInput()?.nativeElement;

    // Arrow navigation - works from search field or when no input focused
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

    // Enter selects first contact if none selected
    if (event.key === 'Enter' && isSearchFocused) {
      event.preventDefault();
      const list = this.filteredContacts();
      if (list.length > 0 && !this.selectedContactId()) {
        this.selectContactById(list[0].id);
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

    this.selectContactById(list[newIndex].id);
  }

  selectContact(contact: PersonaListItem): void {
    this.selectContactById(contact.id);
  }

  async selectContactById(id: string): Promise<void> {
    if (this.selectedContactId() === id) {
      this.mobileShowDetail.set(true);
      return;
    }

    this.selectedContactId.set(id);
    this.selectedContact.set(null);
    this.mobileShowDetail.set(true);

    try {
      const contact = await this.contactsService.getById(id);
      // Only set if still selected (user might have clicked elsewhere)
      if (this.selectedContactId() === id) {
        this.selectedContact.set(contact);
      }
    } catch {
      // Error is handled by service
    }
  }

  createNewContact(): void {
    // Create a new empty persona
    const newPersona: Persona = {
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
    };

    // Deselect current and show new contact form
    this.selectedContactId.set(null);
    this.selectedContact.set(newPersona);
    this.mobileShowDetail.set(true);
  }

  async onContactSaved(contact: Persona): Promise<void> {
    try {
      let savedContact: Persona;

      if (!contact.id) {
        // Create new contact
        savedContact = await this.contactsService.create(contact);
      } else {
        // Update existing contact
        savedContact = await this.contactsService.update(contact.id, contact);

        // Handle bits - compare with current and sync
        const currentContact = this.selectedContact();
        if (currentContact) {
          await this.syncBits(contact.id, currentContact.bits, contact.bits);
          // Reload to get fresh data
          savedContact = await this.contactsService.getById(contact.id);
        }
      }

      this.selectedContactId.set(savedContact.id);
      this.selectedContact.set(savedContact);
    } catch {
      // Error is handled by service
    }
  }

  async onBitAdded(event: { bit: ContactBit; password?: string }): Promise<void> {
    const contactId = this.selectedContactId();
    if (!contactId) return;

    try {
      const updatedPersona = await this.contactsService.addBit(
        contactId,
        event.bit,
        event.password
      );
      this.selectedContact.set(updatedPersona);
    } catch {
      // Error is handled by service
    }
  }

  async onBitUpdated(event: {
    bitId: string;
    changes: Partial<ContactBit>;
    password?: string;
    clearPassword?: boolean;
  }): Promise<void> {
    const contactId = this.selectedContactId();
    if (!contactId) return;

    try {
      // Pass changes directly - the service's toBitUpdate handles the transform
      const changes: Partial<ContactBit> & { password?: string; clearPassword?: boolean } = {
        ...event.changes,
      };

      // Add password fields if present
      if (event.password) {
        changes.password = event.password;
      }
      if (event.clearPassword) {
        changes.clearPassword = true;
      }

      const updatedPersona = await this.contactsService.updateBit(
        contactId,
        event.bitId,
        changes
      );
      this.selectedContact.set(updatedPersona);
    } catch {
      // Error is handled by service
    }
  }

  async onBitDeleted(event: { bitId: string }): Promise<void> {
    const contactId = this.selectedContactId();
    if (!contactId) return;

    try {
      await this.contactsService.deleteBit(contactId, event.bitId);
      // Reload contact to get fresh data
      const updatedContact = await this.contactsService.getById(contactId);
      this.selectedContact.set(updatedContact);
    } catch {
      // Error is handled by service
    }
  }

  async onBitMoved(event: { bitId: string; direction: 'up' | 'down' }): Promise<void> {
    const contact = this.selectedContact();
    if (!contact) return;

    const sorted = [...contact.bits].sort((a, b) => a.bitSequence - b.bitSequence);
    const index = sorted.findIndex(b => b.id === event.bitId);
    if (index < 0) return;

    const swapIndex = event.direction === 'up' ? index - 1 : index + 1;
    if (swapIndex < 0 || swapIndex >= sorted.length) return;

    // Swap bit sequences
    const current = sorted[index];
    const other = sorted[swapIndex];

    try {
      const updatedPersona = await this.contactsService.reorderBits(contact.id, [
        { id: current.id, bitSequence: other.bitSequence },
        { id: other.id, bitSequence: current.bitSequence },
      ]);
      this.selectedContact.set(updatedPersona);
    } catch {
      // Error is handled by service
    }
  }

  /**
   * Sync bits between old and new state
   */
  private async syncBits(
    contactId: string,
    oldBits: Persona['bits'],
    newBits: Persona['bits']
  ): Promise<void> {
    const oldIds = new Set(oldBits.map(b => b.id));
    const newIds = new Set(newBits.map(b => b.id));

    // Delete removed bits
    for (const oldBit of oldBits) {
      if (!newIds.has(oldBit.id)) {
        await this.contactsService.deleteBit(contactId, oldBit.id);
      }
    }

    // Add new bits (IDs starting with 'new-')
    for (const newBit of newBits) {
      if (newBit.id.startsWith('new-')) {
        await this.contactsService.addBit(contactId, newBit);
      }
    }

    // Update existing bits that changed
    for (const newBit of newBits) {
      if (!newBit.id.startsWith('new-') && oldIds.has(newBit.id)) {
        const oldBit = oldBits.find(b => b.id === newBit.id);
        if (oldBit && JSON.stringify(oldBit) !== JSON.stringify(newBit)) {
          await this.contactsService.updateBit(contactId, newBit.id, newBit);
        }
      }
    }
  }

  // Display helpers for list items
  getDisplayName(contact: PersonaListItem): string {
    return contact.entityName;
  }

  getSubtitle(contact: PersonaListItem): string {
    if (contact.isCorporate) {
      return 'Company';
    }
    return contact.organization || '';
  }

  trackById(_index: number, contact: PersonaListItem): string {
    return contact.id;
  }

  /** Refresh the currently selected contact */
  async refreshSelectedContact(): Promise<void> {
    const contactId = this.selectedContactId();
    if (!contactId) return;

    try {
      const contact = await this.contactsService.getById(contactId);
      this.selectedContact.set(contact);
    } catch {
      // Error is handled by service
    }
  }
}
