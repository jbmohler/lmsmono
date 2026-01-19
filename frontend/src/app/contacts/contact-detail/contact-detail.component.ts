import { Component, input, output, signal, computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  Persona,
  ContactBit,
  ContactEmail,
  ContactPhone,
  ContactAddress,
  ContactUrl,
} from '../contacts.model';

@Component({
  selector: 'app-contact-detail',
  templateUrl: './contact-detail.component.html',
  styleUrl: './contact-detail.component.scss',
  imports: [FormsModule],
  host: {
    '(keydown)': 'handleKeydown($event)',
  },
})
export class ContactDetailComponent {
  contact = input.required<Persona>();
  contactSaved = output<Persona>();

  isEditing = signal(false);

  // Edit state - deep copy of contact for editing
  editData = signal<Persona | null>(null);

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

  // Sorted bits for edit mode
  editSortedBits = computed(() => {
    const data = this.editData();
    if (!data) return [];
    return [...data.bits].sort((a, b) => a.bitSequence - b.bitSequence);
  });

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

  // Generic bit operations
  addBit(bitType: ContactBit['bitType']): void {
    this.editData.update(data => {
      if (!data) return data;

      // Get max sequence to place new bit at end
      const maxSeq = data.bits.reduce((max, b) => Math.max(max, b.bitSequence), 0);
      const baseProps = {
        id: `new-${Date.now()}`,
        label: '',
        memo: '',
        isPrimary: data.bits.filter(b => b.bitType === bitType).length === 0,
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
          newBit = { ...baseProps, bitType: 'url', url: '', username: '' };
          break;
      }

      return { ...data, bits: [...data.bits, newBit] };
    });
  }

  updateBit(id: string, field: string, value: string | boolean): void {
    this.editData.update(data => {
      if (!data) return data;
      return {
        ...data,
        bits: data.bits.map(b => b.id === id ? { ...b, [field]: value } : b),
      };
    });
  }

  removeBit(id: string): void {
    this.editData.update(data => {
      if (!data) return data;
      return { ...data, bits: data.bits.filter(b => b.id !== id) };
    });
  }

  setPrimary(id: string, bitType: ContactBit['bitType']): void {
    this.editData.update(data => {
      if (!data) return data;
      return {
        ...data,
        bits: data.bits.map(b => {
          if (b.bitType !== bitType) return b;
          return { ...b, isPrimary: b.id === id };
        }),
      };
    });
  }

  moveBitUp(id: string): void {
    this.editData.update(data => {
      if (!data) return data;

      const sorted = [...data.bits].sort((a, b) => a.bitSequence - b.bitSequence);
      const index = sorted.findIndex(b => b.id === id);
      if (index <= 0) return data;

      // Swap bitSequence values with the item above
      const current = sorted[index];
      const above = sorted[index - 1];

      return {
        ...data,
        bits: data.bits.map(b => {
          if (b.id === current.id) return { ...b, bitSequence: above.bitSequence };
          if (b.id === above.id) return { ...b, bitSequence: current.bitSequence };
          return b;
        }),
      };
    });
  }

  moveBitDown(id: string): void {
    this.editData.update(data => {
      if (!data) return data;

      const sorted = [...data.bits].sort((a, b) => a.bitSequence - b.bitSequence);
      const index = sorted.findIndex(b => b.id === id);
      if (index < 0 || index >= sorted.length - 1) return data;

      // Swap bitSequence values with the item below
      const current = sorted[index];
      const below = sorted[index + 1];

      return {
        ...data,
        bits: data.bits.map(b => {
          if (b.id === current.id) return { ...b, bitSequence: below.bitSequence };
          if (b.id === below.id) return { ...b, bitSequence: current.bitSequence };
          return b;
        }),
      };
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
}
