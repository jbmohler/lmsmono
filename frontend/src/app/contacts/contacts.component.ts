import { Component, signal, computed, viewChild, ElementRef, afterNextRender } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ContactDetailComponent } from './contact-detail/contact-detail.component';
import { Persona, ContactEmail } from './contacts.model';

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
  searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');

  searchQuery = signal('');
  selectedContactId = signal<string | null>(null);

  constructor() {
    afterNextRender(() => {
      this.searchInput()?.nativeElement.focus();
    });
  }

  // Mock contact data
  contacts = signal<Persona[]>([
    {
      id: '1',
      firstName: 'John',
      lastName: 'Doe',
      title: 'Mr.',
      organization: 'Acme Corporation',
      memo: 'Met at tech conference 2024',
      birthday: '1985-03-15',
      anniversary: null,
      isCorporate: false,
      bits: [
        { id: 'e1', bitType: 'email', email: 'john.doe@acme.com', label: 'Work', memo: '', isPrimary: true, bitSequence: 100 },
        { id: 'p1', bitType: 'phone', number: '(555) 123-4567', label: 'Mobile', memo: '', isPrimary: true, bitSequence: 110 },
        { id: 'e2', bitType: 'email', email: 'johndoe@gmail.com', label: 'Personal', memo: '', isPrimary: false, bitSequence: 120 },
        { id: 'p2', bitType: 'phone', number: '(555) 987-6543', label: 'Work', memo: 'Extension 234', isPrimary: false, bitSequence: 130 },
        { id: 'a1', bitType: 'address', address1: '123 Main Street', address2: 'Suite 400', city: 'Springfield', state: 'IL', zip: '62701', country: 'USA', label: 'Work', memo: '', isPrimary: true, bitSequence: 140 },
        { id: 'u1', bitType: 'url', url: 'https://linkedin.com/in/johndoe', username: '', label: 'LinkedIn', memo: '', isPrimary: true, bitSequence: 150 },
      ],
    },
    {
      id: '2',
      firstName: '',
      lastName: 'Acme Corporation',
      title: '',
      organization: '',
      memo: 'Primary vendor for office supplies',
      birthday: null,
      anniversary: null,
      isCorporate: true,
      bits: [
        { id: 'p3', bitType: 'phone', number: '(800) 555-ACME', label: 'Toll Free', memo: '', isPrimary: true, bitSequence: 100 },
        { id: 'e3', bitType: 'email', email: 'info@acme.com', label: 'General', memo: '', isPrimary: true, bitSequence: 110 },
        { id: 'u2', bitType: 'url', url: 'https://acme.com', username: '', label: 'Website', memo: '', isPrimary: true, bitSequence: 120 },
        { id: 'e4', bitType: 'email', email: 'support@acme.com', label: 'Support', memo: '', isPrimary: false, bitSequence: 130 },
        { id: 'e5', bitType: 'email', email: 'billing@acme.com', label: 'Billing', memo: '', isPrimary: false, bitSequence: 140 },
        { id: 'a2', bitType: 'address', address1: '1000 Corporate Blvd', address2: '', city: 'Chicago', state: 'IL', zip: '60601', country: 'USA', label: 'Headquarters', memo: '', isPrimary: true, bitSequence: 150 },
        { id: 'u3', bitType: 'url', url: 'https://portal.acme.com', username: 'johnd', label: 'Vendor Portal', memo: 'Use SSO login', isPrimary: false, bitSequence: 160 },
      ],
    },
    {
      id: '3',
      firstName: 'Jane',
      lastName: 'Smith',
      title: 'Dr.',
      organization: 'City Medical Center',
      memo: '',
      birthday: null,
      anniversary: null,
      isCorporate: false,
      bits: [
        { id: 'p4', bitType: 'phone', number: '(555) 234-5678', label: 'Office', memo: '', isPrimary: true, bitSequence: 100 },
        { id: 'e6', bitType: 'email', email: 'jane.smith@citymed.org', label: 'Work', memo: '', isPrimary: true, bitSequence: 110 },
      ],
    },
    {
      id: '4',
      firstName: 'Bob',
      lastName: 'Wilson',
      title: '',
      organization: 'Wilson & Associates',
      memo: 'Attorney - handles business contracts',
      birthday: null,
      anniversary: null,
      isCorporate: false,
      bits: [
        { id: 'p5', bitType: 'phone', number: '(555) 345-6789', label: 'Office', memo: '', isPrimary: true, bitSequence: 100 },
        { id: 'e7', bitType: 'email', email: 'bob@wilsonlaw.com', label: 'Work', memo: '', isPrimary: true, bitSequence: 110 },
        { id: 'a3', bitType: 'address', address1: '500 Legal Plaza', address2: 'Floor 12', city: 'Springfield', state: 'IL', zip: '62702', country: 'USA', label: 'Office', memo: '', isPrimary: true, bitSequence: 120 },
        { id: 'p6', bitType: 'phone', number: '(555) 345-6780', label: 'Fax', memo: '', isPrimary: false, bitSequence: 130 },
      ],
    },
    {
      id: '5',
      firstName: 'Sarah',
      lastName: 'Johnson',
      title: 'Ms.',
      organization: '',
      memo: 'Neighbor - can receive packages',
      birthday: '1990-07-22',
      anniversary: null,
      isCorporate: false,
      bits: [
        { id: 'p7', bitType: 'phone', number: '(555) 456-7890', label: 'Mobile', memo: '', isPrimary: true, bitSequence: 100 },
        { id: 'e8', bitType: 'email', email: 'sarah.j@email.com', label: 'Personal', memo: '', isPrimary: true, bitSequence: 110 },
        { id: 'a4', bitType: 'address', address1: '125 Main Street', address2: '', city: 'Springfield', state: 'IL', zip: '62701', country: 'USA', label: 'Home', memo: '', isPrimary: true, bitSequence: 120 },
      ],
    },
  ]);

  filteredContacts = computed(() => {
    const query = this.searchQuery().toLowerCase();
    if (!query) return this.contacts();

    return this.contacts().filter(c => {
      const name = this.getDisplayName(c).toLowerCase();
      const org = c.organization.toLowerCase();
      const emails = c.bits
        .filter((b): b is ContactEmail => b.bitType === 'email')
        .map(e => e.email.toLowerCase())
        .join(' ');
      return name.includes(query) || org.includes(query) || emails.includes(query);
    });
  });

  selectedContact = computed(() => {
    const id = this.selectedContactId();
    if (!id) return null;
    return this.contacts().find(c => c.id === id) ?? null;
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
      const isOtherInputFocused = !isSearchFocused &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT');

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
        this.selectedContactId.set(list[0].id);
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

    this.selectedContactId.set(list[newIndex].id);
  }

  selectContact(contact: Persona): void {
    this.selectedContactId.set(contact.id);
  }

  createNewContact(): void {
    // TODO: Create new contact and select it
    console.log('Create new contact');
  }

  onContactSaved(contact: Persona): void {
    // TODO: Save to API
    this.contacts.update(contacts =>
      contacts.map(c => c.id === contact.id ? contact : c)
    );
  }

  getDisplayName(contact: Persona): string {
    if (contact.isCorporate) {
      return contact.lastName;
    }
    return [contact.title, contact.firstName, contact.lastName].filter(Boolean).join(' ');
  }

  getSubtitle(contact: Persona): string {
    if (contact.isCorporate) {
      return 'Company';
    }
    return contact.organization || '';
  }

  trackById(_index: number, contact: Persona): string {
    return contact.id;
  }
}
