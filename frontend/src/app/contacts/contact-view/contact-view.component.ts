import { Component, input, output, inject, signal, effect } from '@angular/core';
import { Persona, ContactBit } from '../contacts.model';
import { ContactsService } from '../services/contacts.service';
import { ContactDetailComponent } from '../contact-detail/contact-detail.component';

@Component({
  selector: 'app-contact-view',
  templateUrl: './contact-view.component.html',
  styleUrl: './contact-view.component.scss',
  imports: [ContactDetailComponent],
})
export class ContactViewComponent {
  private contactsService = inject(ContactsService);

  contactId = input.required<string>();
  back = output<void>();

  contact = signal<Persona | null>(null);
  loading = signal(false);

  constructor() {
    effect(() => {
      void this.load(this.contactId());
    });
  }

  private async load(id: string): Promise<void> {
    this.contact.set(null);
    this.loading.set(true);
    try {
      const contact = await this.contactsService.getById(id);
      if (this.contactId() === id) {
        this.contact.set(contact);
      }
    } catch {
      // error handled by service
    } finally {
      this.loading.set(false);
    }
  }

  async refresh(): Promise<void> {
    await this.load(this.contactId());
  }

  async onContactSaved(contact: Persona): Promise<void> {
    if (!contact.id) return;
    try {
      this.contact.set(await this.contactsService.update(contact.id, contact));
    } catch {
      // error handled by service
    }
  }

  async onBitAdded(event: { bit: ContactBit; password?: string }): Promise<void> {
    try {
      this.contact.set(
        await this.contactsService.addBit(this.contactId(), event.bit, event.password)
      );
    } catch {
      // error handled by service
    }
  }

  async onBitUpdated(event: {
    bitId: string;
    changes: Partial<ContactBit>;
    password?: string;
    clearPassword?: boolean;
  }): Promise<void> {
    try {
      const changes: Partial<ContactBit> & { password?: string; clearPassword?: boolean } = {
        ...event.changes,
      };
      if (event.password) changes.password = event.password;
      if (event.clearPassword) changes.clearPassword = true;
      this.contact.set(
        await this.contactsService.updateBit(this.contactId(), event.bitId, changes)
      );
    } catch {
      // error handled by service
    }
  }

  async onBitDeleted(event: { bitId: string }): Promise<void> {
    try {
      await this.contactsService.deleteBit(this.contactId(), event.bitId);
      this.contact.set(await this.contactsService.getById(this.contactId()));
    } catch {
      // error handled by service
    }
  }

  async onBitMoved(event: { bitId: string; direction: 'up' | 'down' }): Promise<void> {
    const contact = this.contact();
    if (!contact) return;
    const sorted = [...contact.bits].sort((a, b) => a.bitSequence - b.bitSequence);
    const index = sorted.findIndex(b => b.id === event.bitId);
    if (index < 0) return;
    const swapIndex = event.direction === 'up' ? index - 1 : index + 1;
    if (swapIndex < 0 || swapIndex >= sorted.length) return;
    try {
      this.contact.set(
        await this.contactsService.reorderBits(contact.id, [
          { id: sorted[index].id, bitSequence: sorted[swapIndex].bitSequence },
          { id: sorted[swapIndex].id, bitSequence: sorted[index].bitSequence },
        ])
      );
    } catch {
      // error handled by service
    }
  }
}
