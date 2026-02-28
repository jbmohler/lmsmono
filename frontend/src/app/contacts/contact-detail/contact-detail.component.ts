import { Component, input, output, signal, computed, inject, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  Persona,
  ContactBit,
  ContactEmail,
  ContactPhone,
  ContactAddress,
  ContactUrl,
  PersonaShare,
} from '../contacts.model';
import { BitEditDialogComponent, BitEditResult } from '../bit-edit-dialog/bit-edit-dialog.component';
import { SharingDialogComponent } from '../sharing-dialog/sharing-dialog.component';
import { ContactsService } from '../services/contacts.service';

@Component({
  selector: 'app-contact-detail',
  templateUrl: './contact-detail.component.html',
  styleUrl: './contact-detail.component.scss',
  imports: [FormsModule, BitEditDialogComponent, SharingDialogComponent],
  host: {
    '(keydown)': 'handleKeydown($event)',
  },
})
export class ContactDetailComponent {
  private contactsService = inject(ContactsService);

  contact = input.required<Persona>();
  back = output<void>();
  contactSaved = output<Persona>();
  contactRefresh = output<void>();
  bitUpdated = output<{ bitId: string; changes: Partial<ContactBit>; password?: string; clearPassword?: boolean }>();
  bitAdded = output<{ bit: ContactBit; password?: string }>();
  bitDeleted = output<{ bitId: string }>();
  bitMoved = output<{ bitId: string; direction: 'up' | 'down' }>();

  isEditing = signal(false);

  // Edit state - deep copy of contact for editing
  editData = signal<Persona | null>(null);

  // Bit dialog state
  editingBit = signal<ContactBit | null>(null);

  // Sharing state
  shares = signal<PersonaShare[]>([]);
  sharesLoading = signal(false);
  showSharingDialog = signal(false);

  // Password copy feedback
  copyingPasswordId = signal<string | null>(null);

  displayName = computed(() => {
    const c = this.contact();
    if (c.isCorporate) {
      return c.lastName;
    }
    return [c.title, c.firstName, c.lastName].filter(Boolean).join(' ');
  });

  // Sorted bits for view mode
  sortedBits = computed(() => {
    return [...this.contact().bits].sort((a, b) => a.bitSequence - b.bitSequence);
  });

  constructor() {
    effect(() => {
      const id = this.contact().id;
      if (id) {
        this.loadShares();
      }
    });
  }

  handleKeydown(event: KeyboardEvent): void {
    // Escape to exit edit mode
    if (event.key === 'Escape' && this.isEditing()) {
      event.preventDefault();
      this.cancelEdit();
    }

    // Ctrl+S to save
    if (event.ctrlKey && event.key === 's' && this.isEditing()) {
      event.preventDefault();
      this.saveEdit();
    }
  }

  enterEditMode(): void {
    // Deep copy the contact for editing
    this.editData.set(JSON.parse(JSON.stringify(this.contact())));
    this.isEditing.set(true);
  }

  cancelEdit(): void {
    this.editData.set(null);
    this.isEditing.set(false);
  }

  saveEdit(): void {
    const data = this.editData();
    if (data) {
      this.contactSaved.emit(data);
    }
    this.isEditing.set(false);
    this.editData.set(null);
  }

  // Edit helpers
  updateField(field: keyof Persona, value: string | boolean): void {
    this.editData.update(data => {
      if (!data) return data;
      return { ...data, [field]: value };
    });
  }

  // Type guards for templates
  isEmail(bit: ContactBit): bit is ContactEmail {
    return bit.bitType === 'email';
  }

  isPhone(bit: ContactBit): bit is ContactPhone {
    return bit.bitType === 'phone';
  }

  isAddress(bit: ContactBit): bit is ContactAddress {
    return bit.bitType === 'address';
  }

  isUrl(bit: ContactBit): bit is ContactUrl {
    return bit.bitType === 'url';
  }

  formatAddress(addr: ContactAddress): string {
    const parts = [addr.address1];
    if (addr.address2) parts.push(addr.address2);
    const cityLine = [addr.city, addr.state, addr.zip].filter(Boolean).join(', ');
    if (cityLine) parts.push(cityLine);
    if (addr.country && addr.country !== 'USA') parts.push(addr.country);
    return parts.join('\n');
  }

  getBitTypeLabel(bitType: ContactBit['bitType']): string {
    switch (bitType) {
      case 'email': return 'Email';
      case 'phone': return 'Phone';
      case 'address': return 'Address';
      case 'url': return 'Link';
    }
  }

  trackById(_index: number, item: { id: string }): string {
    return item.id;
  }

  // Bit dialog operations
  openBitDialog(bit: ContactBit): void {
    this.editingBit.set(bit);
  }

  closeBitDialog(): void {
    this.editingBit.set(null);
  }

  /** Create a new bit template and open the dialog (for view mode) */
  addBitFromView(bitType: ContactBit['bitType']): void {
    const maxSeq = this.contact().bits.reduce((max, b) => Math.max(max, b.bitSequence), 0);
    const baseProps = {
      id: `new-${Date.now()}`,
      label: '',
      memo: '',
      isPrimary: this.contact().bits.filter(b => b.bitType === bitType).length === 0,
      bitSequence: maxSeq + 10,
    };

    let newBit: ContactBit;
    switch (bitType) {
      case 'email':
        newBit = { ...baseProps, bitType: 'email', email: '' };
        break;
      case 'phone':
        newBit = { ...baseProps, bitType: 'phone', number: '' };
        break;
      case 'address':
        newBit = {
          ...baseProps,
          bitType: 'address',
          address1: '',
          address2: '',
          city: '',
          state: '',
          zip: '',
          country: '',
        };
        break;
      case 'url':
        newBit = {
          ...baseProps,
          bitType: 'url',
          url: '',
          username: '',
          hasPassword: false,
          pwResetDt: null,
          pwNextResetDt: null,
        };
        break;
    }

    this.editingBit.set(newBit);
  }

  async saveBitFromDialog(result: BitEditResult): Promise<void> {
    const { bit, password, clearPassword, isNew } = result;
    this.editingBit.set(null);

    // In view mode, emit to parent
    if (isNew) {
      this.bitAdded.emit({ bit, password });
    } else {
      this.bitUpdated.emit({
        bitId: bit.id,
        changes: bit,
        password,
        clearPassword,
      });
    }
  }

  /** Confirm and delete a bit (view mode) */
  confirmDeleteBit(bit: ContactBit): void {
    const typeLabel = this.getBitTypeLabel(bit.bitType).toLowerCase();
    const confirmed = window.confirm(`Delete this ${typeLabel}?`);
    if (confirmed) {
      this.bitDeleted.emit({ bitId: bit.id });
    }
  }

  /** Move a bit up or down (view mode) */
  moveBitFromView(bitId: string, direction: 'up' | 'down'): void {
    this.bitMoved.emit({ bitId, direction });
  }

  /** Check if a URL bit's password is expired */
  isPasswordExpired(bit: ContactBit): boolean {
    if (bit.bitType !== 'url') return false;
    const urlBit = bit as ContactUrl;
    if (!urlBit.pwNextResetDt) return false;
    const expirationDate = new Date(urlBit.pwNextResetDt);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return expirationDate < today;
  }

  /** Copy password to clipboard (view mode) */
  async copyPassword(bit: ContactBit): Promise<void> {
    if (bit.bitType !== 'url') return;
    const urlBit = bit as ContactUrl;
    if (!urlBit.hasPassword) return;

    try {
      const password = await this.contactsService.getPassword(
        this.contact().id,
        bit.id
      );
      await navigator.clipboard.writeText(password);
      this.copyingPasswordId.set(bit.id);
      setTimeout(() => this.copyingPasswordId.set(null), 2000);
    } catch {
      // Error is handled by service
    }
  }

  // Sharing operations
  async loadShares(): Promise<void> {
    this.sharesLoading.set(true);
    try {
      const shares = await this.contactsService.getShares(this.contact().id);
      this.shares.set(shares);
    } finally {
      this.sharesLoading.set(false);
    }
  }

  openSharingDialog(): void {
    this.showSharingDialog.set(true);
  }

  closeSharingDialog(): void {
    this.showSharingDialog.set(false);
  }

  onSharesChanged(): void {
    this.loadShares();
    this.contactRefresh.emit();
  }
}
