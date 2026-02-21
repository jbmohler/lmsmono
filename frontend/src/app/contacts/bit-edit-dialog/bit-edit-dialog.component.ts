import {
  Component,
  input,
  output,
  signal,
  inject,
  viewChild,
  ElementRef,
  afterNextRender,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  ContactBit,
  ContactEmail,
  ContactPhone,
  ContactAddress,
  ContactUrl,
} from '../contacts.model';
import { ContactsService } from '../services/contacts.service';
import { PasswordGeneratorService } from '../services/password-generator.service';

export interface BitEditResult {
  bit: ContactBit;
  password?: string;
  clearPassword?: boolean;
  isNew?: boolean;
}

@Component({
  selector: 'app-bit-edit-dialog',
  templateUrl: './bit-edit-dialog.component.html',
  styleUrl: './bit-edit-dialog.component.scss',
  imports: [FormsModule],
  host: {
    '(keydown)': 'handleKeydown($event)',
  },
})
export class BitEditDialogComponent {
  private contactsService = inject(ContactsService);
  private passwordGenerator = inject(PasswordGeneratorService);

  contactId = input.required<string>();
  bit = input.required<ContactBit>();

  saved = output<BitEditResult>();
  cancelled = output<void>();

  dialogEl = viewChild<ElementRef<HTMLDialogElement>>('dialog');

  // Form state - clone of input bit
  editBit = signal<ContactBit | null>(null);

  // Loading state for fetching fresh data
  loading = signal(false);

  // Password handling for URL bits
  passwordVisible = signal(false);
  decryptedPassword = signal<string | null>(null);
  newPassword = signal<string>('');
  showPasswordChange = signal(false);
  clearPassword = signal(false);
  copyFeedback = signal(false);

  // Password generator
  generatorMode = signal('alphanumeric');
  generatorBits = signal(50);
  showGenerator = signal(false);
  generating = signal(false);

  constructor() {
    afterNextRender(() => {
      this.open();
    });
  }

  /** Check if this is a new bit (not yet saved to backend) */
  isNewBit(): boolean {
    return this.bit().id.startsWith('new-');
  }

  async open(): Promise<void> {
    this.passwordVisible.set(false);
    this.decryptedPassword.set(null);
    this.newPassword.set('');
    this.showPasswordChange.set(false);
    this.clearPassword.set(false);
    this.generatorMode.set('alphanumeric');
    this.generatorBits.set(50);
    this.showGenerator.set(false);
    this.generating.set(false);

    const dialog = this.dialogEl()?.nativeElement;
    if (dialog && !dialog.open) {
      dialog.showModal();
    }

    // For new bits, just use the template. For existing bits, load fresh data.
    if (this.isNewBit()) {
      this.editBit.set(JSON.parse(JSON.stringify(this.bit())));
    } else {
      // Load fresh data from backend
      this.loading.set(true);
      try {
        const freshBit = await this.contactsService.getBit(
          this.contactId(),
          this.bit().id
        );
        this.editBit.set(freshBit);
      } catch {
        // On error, fall back to the input bit
        this.editBit.set(JSON.parse(JSON.stringify(this.bit())));
      } finally {
        this.loading.set(false);
      }
    }
  }

  close(): void {
    const dialog = this.dialogEl()?.nativeElement;
    if (dialog?.open) {
      dialog.close();
    }
    this.cancelled.emit();
  }

  save(): void {
    const bit = this.editBit();
    if (!bit) return;

    const result: BitEditResult = { bit, isNew: this.isNewBit() };

    // Handle password for URL bits
    if (bit.bitType === 'url') {
      if (this.clearPassword()) {
        result.clearPassword = true;
      } else if (this.newPassword()) {
        result.password = this.newPassword();
      }
    }

    const dialog = this.dialogEl()?.nativeElement;
    if (dialog?.open) {
      dialog.close();
    }
    this.saved.emit(result);
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.close();
    }
    if (event.ctrlKey && event.key === 's') {
      event.preventDefault();
      this.save();
    }
  }

  // Field update helpers
  updateField(field: string, value: string | boolean): void {
    this.editBit.update(bit => {
      if (!bit) return bit;
      return { ...bit, [field]: value };
    });
  }

  // Password operations for URL bits
  async togglePasswordVisibility(): Promise<void> {
    if (this.passwordVisible()) {
      this.passwordVisible.set(false);
      return;
    }

    const bit = this.editBit();
    if (!bit || bit.bitType !== 'url') return;

    const urlBit = bit as ContactUrl;
    if (!urlBit.hasPassword) return;

    // Fetch password if not already loaded
    if (!this.decryptedPassword()) {
      try {
        const password = await this.contactsService.getPassword(
          this.contactId(),
          bit.id
        );
        this.decryptedPassword.set(password);
      } catch {
        return;
      }
    }

    this.passwordVisible.set(true);
  }

  async copyPassword(): Promise<void> {
    const bit = this.editBit();
    if (!bit || bit.bitType !== 'url') return;

    const urlBit = bit as ContactUrl;
    if (!urlBit.hasPassword) return;

    // Fetch password if not already loaded
    let password = this.decryptedPassword();
    if (!password) {
      try {
        password = await this.contactsService.getPassword(
          this.contactId(),
          bit.id
        );
        this.decryptedPassword.set(password);
      } catch {
        return;
      }
    }

    await navigator.clipboard.writeText(password);
    this.copyFeedback.set(true);
    setTimeout(() => this.copyFeedback.set(false), 2000);
  }

  toggleGenerator(): void {
    this.showGenerator.update(v => !v);
  }

  generatePassword(): void {
    this.generating.set(true);
    this.passwordGenerator.generate(this.generatorMode(), this.generatorBits()).subscribe({
      next: (password) => {
        this.newPassword.set(password);

        // Auto-update password dates
        const bit = this.editBit();
        if (bit && bit.bitType === 'url') {
          const urlBit = bit as ContactUrl;
          const today = new Date().toISOString().slice(0, 10);

          if (urlBit.pwResetDt && urlBit.pwNextResetDt) {
            const lastReset = new Date(urlBit.pwResetDt);
            const nextReset = new Date(urlBit.pwNextResetDt);
            const intervalDays = Math.round(
              (nextReset.getTime() - lastReset.getTime()) / (1000 * 60 * 60 * 24),
            );
            const newNext = new Date();
            newNext.setDate(newNext.getDate() + intervalDays);
            this.updateField('pwResetDt', today);
            this.updateField('pwNextResetDt', newNext.toISOString().slice(0, 10));
          } else {
            const newNext = new Date();
            newNext.setDate(newNext.getDate() + 365);
            this.updateField('pwResetDt', today);
            this.updateField('pwNextResetDt', newNext.toISOString().slice(0, 10));
          }
        }

        this.generating.set(false);
      },
      error: () => {
        this.generating.set(false);
      },
    });
  }

  togglePasswordChange(): void {
    this.showPasswordChange.update(v => !v);
    if (!this.showPasswordChange()) {
      this.newPassword.set('');
      this.clearPassword.set(false);
    }
  }

  // Type guards
  isEmail(): boolean {
    return this.editBit()?.bitType === 'email';
  }

  isPhone(): boolean {
    return this.editBit()?.bitType === 'phone';
  }

  isAddress(): boolean {
    return this.editBit()?.bitType === 'address';
  }

  isUrl(): boolean {
    return this.editBit()?.bitType === 'url';
  }

  getDialogTitle(): string {
    const bit = this.editBit();
    if (!bit) return this.isNewBit() ? 'Add' : 'Edit';
    const action = this.isNewBit() ? 'Add' : 'Edit';
    switch (bit.bitType) {
      case 'email': return `${action} Email`;
      case 'phone': return `${action} Phone`;
      case 'address': return `${action} Address`;
      case 'url': return `${action} Link`;
    }
  }

  // Typed accessors for templates
  get emailBit(): ContactEmail | null {
    const bit = this.editBit();
    return bit?.bitType === 'email' ? bit as ContactEmail : null;
  }

  get phoneBit(): ContactPhone | null {
    const bit = this.editBit();
    return bit?.bitType === 'phone' ? bit as ContactPhone : null;
  }

  get addressBit(): ContactAddress | null {
    const bit = this.editBit();
    return bit?.bitType === 'address' ? bit as ContactAddress : null;
  }

  get urlBit(): ContactUrl | null {
    const bit = this.editBit();
    return bit?.bitType === 'url' ? bit as ContactUrl : null;
  }

  isOverdue(dateStr: string | null): boolean {
    if (!dateStr) return false;
    const date = new Date(dateStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return date < today;
  }
}
