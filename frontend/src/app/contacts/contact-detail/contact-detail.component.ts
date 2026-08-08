import { Component, input, output, signal, computed, inject, effect, viewChild, ElementRef, DestroyRef, Pipe, PipeTransform, ChangeDetectionStrategy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  Persona,
  ContactBit,
  ContactEmail,
  ContactPhone,
  ContactAddress,
  ContactUrl,
  ContactTag,
} from '../contacts.model';
import { BitEditDialogComponent, BitEditResult } from '../bit-edit-dialog/bit-edit-dialog.component';
import { SharingDialogComponent } from '../sharing-dialog/sharing-dialog.component';
import { ContactsService } from '../services/contacts.service';
import { TagSelectorComponent } from '@shared/components/tag-selector/tag-selector.component';

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
    TagSelectorComponent,
    AsEmailPipe,
    AsPhonePipe,
    AsAddressPipe,
    AsUrlPipe,
    FormatAddressPipe,
    IsPasswordExpiredPipe,
    MemoNeedsExpandPipe,
  ],
  changeDetection: ChangeDetectionStrategy.Eager,
  host: {
    // window-scoped: after clicking a contact, focus sits on body, so an
    // element-scoped listener would never see these keys
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class ContactDetailComponent {
  private contactsService = inject(ContactsService);

  contact = input.required<Persona>();
  startInEditMode = input(false);
  back = output<void>();
  contactSaved = output<Persona>();
  contactDeleted = output<void>();
  contactRefresh = output<void>();
  bitUpdated = output<{ bitId: string; changes: Partial<ContactBit>; password?: string; clearPassword?: boolean }>();
  bitAdded = output<{ bit: ContactBit; password?: string }>();
  bitDeleted = output<{ bitId: string }>();
  bitMoved = output<{ bitId: string; direction: 'up' | 'down' }>();

  isEditing = signal(false);
  editData = signal<Persona | null>(null);

  localContactTags = signal<ContactTag[]>([]);

  // First name for an individual, company name for a corporate entity —
  // whichever is rendered first in the edit form.
  private nameInput = viewChild<ElementRef<HTMLInputElement>>('nameInput');
  private pendingNameFocus = signal(false);

  constructor() {
    effect(() => {
      // Track contact() so a fresh new-contact (Ctrl+Shift+N pressed again while
      // the blank form is open) re-clones the form and re-focuses the name field.
      this.contact();
      if (this.startInEditMode()) this.enterEditMode();
    });
    effect(() => {
      const el = this.nameInput();
      if (el && this.pendingNameFocus()) {
        this.pendingNameFocus.set(false);
        el.nativeElement.focus();
      }
    });
    effect(() => {
      // Sync local tag state when contact changes
      this.localContactTags.set(this.contact().tags ?? []);
    });
    void this.contactsService.loadTagTree();

    inject(DestroyRef).onDestroy(() => clearTimeout(this.hotkeyMessageTimer));
  }
  editingBit = signal<ContactBit | null>(null);
  shares = computed(() => this.contact().shares ?? []);
  showSharingDialog = signal(false);

  allTags = this.contactsService.tagTree;
  contactTagIds = computed(() => this.localContactTags().map(t => t.id));
  showTagPopover = signal(false);

  sortedContactTags = computed(() => {
    const selected = this.localContactTags();
    const allMap = new Map((this.allTags() ?? []).map(t => [t.id, t]));
    const depth = (id: string, seen = new Set<string>()): number => {
      if (seen.has(id)) return 0;
      const t = allMap.get(id);
      if (!t?.parentId) return 0;
      seen.add(id);
      return 1 + depth(t.parentId, seen);
    };
    return [...selected].sort((a, b) => {
      const diff = depth(a.id) - depth(b.id);
      return diff !== 0 ? diff : a.name.localeCompare(b.name);
    });
  });
  copyingPasswordId = signal<string | null>(null);

  displayName = computed(() => {
    const c = this.contact();
    if (c.isCorporate) return c.lastName;
    return [c.title, c.firstName, c.lastName].filter(Boolean).join(' ');
  });

  sortedBits = computed(() =>
    [...this.contact().bits].sort((a, b) => a.bitSequence - b.bitSequence)
  );

  /** "First" means first as displayed, i.e. lowest bit sequence. */
  private firstUrlBit(predicate: (bit: ContactUrl) => boolean): ContactUrl | null {
    for (const bit of this.sortedBits()) {
      if (bit.bitType === 'url' && predicate(bit)) return bit;
    }
    return null;
  }

  firstPasswordBit = computed(() => this.firstUrlBit(bit => bit.hasPassword));
  firstLinkBit = computed(() => this.firstUrlBit(bit => !!bit.url));

  /** Transient feedback for shortcuts that had nothing to act on. */
  hotkeyMessage = signal<string | null>(null);
  private hotkeyMessageTimer?: ReturnType<typeof setTimeout>;

  private flashMessage(message: string): void {
    this.hotkeyMessage.set(message);
    clearTimeout(this.hotkeyMessageTimer);
    this.hotkeyMessageTimer = setTimeout(() => this.hotkeyMessage.set(null), 2000);
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && this.isEditing()) {
      event.preventDefault();
      this.cancelEdit();
    }
    if (event.ctrlKey && event.key === 's' && this.isEditing()) {
      event.preventDefault();
      this.saveEdit();
    }

    // Single-letter shortcuts, matching the 's' convention on the contact list.
    // Never while typing, editing, or with a dialog open.
    const target = event.target as HTMLElement | null;
    const isInInput =
      target?.tagName === 'INPUT' ||
      target?.tagName === 'TEXTAREA' ||
      target?.tagName === 'SELECT' ||
      target?.isContentEditable === true;
    const busy = this.isEditing() || !!this.editingBit() || this.showSharingDialog();
    if (isInInput || busy || event.ctrlKey || event.altKey || event.metaKey) return;

    if (event.key === 'p') {
      event.preventDefault();
      void this.copyFirstPassword();
    }
    if (event.key === 'l') {
      event.preventDefault();
      this.openFirstLink();
    }
  }

  /** Copy the password of the first link that has one. */
  async copyFirstPassword(): Promise<void> {
    const bit = this.firstPasswordBit();
    if (!bit) {
      this.flashMessage('No saved password on this contact');
      return;
    }
    await this.copyPassword(bit);
  }

  /** Open the first link in a new tab. */
  openFirstLink(): void {
    const bit = this.firstLinkBit();
    if (!bit) {
      this.flashMessage('No link on this contact');
      return;
    }
    window.open(bit.url, '_blank', 'noopener,noreferrer');
  }

  enterEditMode(): void {
    this.editData.set(JSON.parse(JSON.stringify(this.contact())));
    this.isEditing.set(true);
    this.pendingNameFocus.set(true);
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

  /**
   * Switch between company and individual. Corporate entities must have no
   * first name and no title (see chk_corp_names in contacts.personas).
   */
  setCorporate(isCorporate: boolean): void {
    this.editData.update(data => {
      if (!data) return data;
      return isCorporate
        ? { ...data, isCorporate, firstName: '', title: '' }
        : { ...data, isCorporate };
    });
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

  /** Delete the whole contact, after confirming — this cannot be undone. */
  confirmDeleteContact(): void {
    const name = this.displayName() || 'this contact';
    if (window.confirm(`Delete ${name} and all of its contact info? This cannot be undone.`)) {
      this.contactDeleted.emit();
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

  async onTagToggled(event: { tagIds: string[]; action: 'add' | 'remove' }): Promise<void> {
    const contactId = this.contact().id;
    try {
      let updatedTags: ContactTag[] = this.localContactTags();
      if (event.action === 'add') {
        updatedTags = await this.contactsService.addContactTag(contactId, event.tagIds[0]);
      } else {
        for (const tagId of event.tagIds) {
          updatedTags = await this.contactsService.removeContactTag(contactId, tagId);
        }
      }
      this.localContactTags.set(updatedTags);
    } catch {
      // error handled by service
    }
  }
}
