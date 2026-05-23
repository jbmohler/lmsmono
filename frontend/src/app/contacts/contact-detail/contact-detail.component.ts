import { Component, input, output, signal, computed, inject, effect, Pipe, PipeTransform } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  Persona,
  ContactBit,
  ContactEmail,
  ContactPhone,
  ContactAddress,
  ContactUrl,
} from '../contacts.model';
import { BitEditDialogComponent, BitEditResult } from '../bit-edit-dialog/bit-edit-dialog.component';
import { SharingDialogComponent } from '../sharing-dialog/sharing-dialog.component';
import { ContactsService } from '../services/contacts.service';

@Pipe({ name: 'asEmail' })
class AsEmailPipe implements PipeTransform {
  transform(bit: ContactBit): ContactEmail | null {
    return bit.bitType === 'email' ? (bit as ContactEmail) : null;
  }
}

@Pipe({ name: 'asPhone' })
class AsPhonePipe implements PipeTransform {
  transform(bit: ContactBit): ContactPhone | null {
    return bit.bitType === 'phone' ? (bit as ContactPhone) : null;
  }
}

@Pipe({ name: 'asAddress' })
class AsAddressPipe implements PipeTransform {
  transform(bit: ContactBit): ContactAddress | null {
    return bit.bitType === 'address' ? (bit as ContactAddress) : null;
  }
}

@Pipe({ name: 'asUrl' })
class AsUrlPipe implements PipeTransform {
  transform(bit: ContactBit): ContactUrl | null {
    return bit.bitType === 'url' ? (bit as ContactUrl) : null;
  }
}

@Pipe({ name: 'formatAddress' })
class FormatAddressPipe implements PipeTransform {
  transform(addr: ContactAddress): string {
    const parts = [addr.address1];
    if (addr.address2) parts.push(addr.address2);
    const cityLine = [addr.city, addr.state, addr.zip].filter(Boolean).join(', ');
    if (cityLine) parts.push(cityLine);
    if (addr.country && addr.country !== 'USA') parts.push(addr.country);
    return parts.join('\n');
  }
}

@Pipe({ name: 'isPasswordExpired' })
class IsPasswordExpiredPipe implements PipeTransform {
  transform(bit: ContactUrl): boolean {
    if (!bit.pwNextResetDt) return false;
    const expiration = new Date(bit.pwNextResetDt);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return expiration < today;
  }
}

@Pipe({ name: 'memoNeedsExpand' })
class MemoNeedsExpandPipe implements PipeTransform {
  transform(memo: string): boolean {
    return memo.split('\n').length > 3 || memo.length > 150;
  }
}

@Component({
  selector: 'app-contact-detail',
  templateUrl: './contact-detail.component.html',
  styleUrl: './contact-detail.component.scss',
  imports: [
    FormsModule,
    BitEditDialogComponent,
    SharingDialogComponent,
    AsEmailPipe,
    AsPhonePipe,
    AsAddressPipe,
    AsUrlPipe,
    FormatAddressPipe,
    IsPasswordExpiredPipe,
    MemoNeedsExpandPipe,
  ],
  host: {
    '(keydown)': 'handleKeydown($event)',
  },
})
export class ContactDetailComponent {
  private contactsService = inject(ContactsService);

  contact = input.required<Persona>();
  startInEditMode = input(false);
  back = output<void>();
  contactSaved = output<Persona>();
  contactRefresh = output<void>();
  bitUpdated = output<{ bitId: string; changes: Partial<ContactBit>; password?: string; clearPassword?: boolean }>();
  bitAdded = output<{ bit: ContactBit; password?: string }>();
  bitDeleted = output<{ bitId: string }>();
  bitMoved = output<{ bitId: string; direction: 'up' | 'down' }>();

  isEditing = signal(false);
  editData = signal<Persona | null>(null);

  constructor() {
    effect(() => {
      if (this.startInEditMode()) this.enterEditMode();
    });
  }
  editingBit = signal<ContactBit | null>(null);
  shares = computed(() => this.contact().shares ?? []);
  showSharingDialog = signal(false);
  copyingPasswordId = signal<string | null>(null);

  displayName = computed(() => {
    const c = this.contact();
    if (c.isCorporate) return c.lastName;
    return [c.title, c.firstName, c.lastName].filter(Boolean).join(' ');
  });

  sortedBits = computed(() =>
    [...this.contact().bits].sort((a, b) => a.bitSequence - b.bitSequence)
  );

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && this.isEditing()) {
      event.preventDefault();
      this.cancelEdit();
    }
    if (event.ctrlKey && event.key === 's' && this.isEditing()) {
      event.preventDefault();
      this.saveEdit();
    }
  }

  enterEditMode(): void {
    this.editData.set(JSON.parse(JSON.stringify(this.contact())));
    this.isEditing.set(true);
  }

  cancelEdit(): void {
    this.editData.set(null);
    this.isEditing.set(false);
  }

  saveEdit(): void {
    const data = this.editData();
    if (data) this.contactSaved.emit(data);
    this.isEditing.set(false);
    this.editData.set(null);
  }

  updateField(field: keyof Persona, value: string | boolean): void {
    this.editData.update(data => data ? { ...data, [field]: value } : data);
  }

  getBitTypeLabel(bitType: ContactBit['bitType']): string {
    switch (bitType) {
      case 'email': return 'Email';
      case 'phone': return 'Phone';
      case 'address': return 'Address';
      case 'url': return 'Link';
    }
  }

  openBitDialog(bit: ContactBit): void {
    this.editingBit.set(bit);
  }

  closeBitDialog(): void {
    this.editingBit.set(null);
  }

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
        newBit = { ...baseProps, bitType: 'address', address1: '', address2: '', city: '', state: '', zip: '', country: '' };
        break;
      case 'url':
        newBit = { ...baseProps, bitType: 'url', url: '', username: '', hasPassword: false, pwResetDt: null, pwNextResetDt: null };
        break;
    }
    this.editingBit.set(newBit);
  }

  async saveBitFromDialog(result: BitEditResult): Promise<void> {
    const { bit, password, clearPassword, isNew } = result;
    this.editingBit.set(null);
    if (isNew) {
      this.bitAdded.emit({ bit, password });
    } else {
      this.bitUpdated.emit({ bitId: bit.id, changes: bit, password, clearPassword });
    }
  }

  confirmDeleteBit(bit: ContactBit): void {
    const typeLabel = this.getBitTypeLabel(bit.bitType).toLowerCase();
    if (window.confirm(`Delete this ${typeLabel}?`)) {
      this.bitDeleted.emit({ bitId: bit.id });
    }
  }

  moveBitFromView(bitId: string, direction: 'up' | 'down'): void {
    this.bitMoved.emit({ bitId, direction });
  }

  async copyPassword(bit: ContactUrl): Promise<void> {
    if (!bit.hasPassword) return;
    try {
      const password = await this.contactsService.getPassword(this.contact().id, bit.id);
      await navigator.clipboard.writeText(password);
      this.copyingPasswordId.set(bit.id);
      setTimeout(() => this.copyingPasswordId.set(null), 2000);
    } catch {
      // error handled by service
    }
  }

  openSharingDialog(): void {
    this.showSharingDialog.set(true);
  }

  closeSharingDialog(): void {
    this.showSharingDialog.set(false);
  }

  onSharesChanged(): void {
    this.contactRefresh.emit();
  }
}
