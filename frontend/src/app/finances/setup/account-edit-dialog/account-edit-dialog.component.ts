import { Component, ElementRef, output, input, viewChild, signal, computed, afterNextRender, inject, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AccountService } from '@finances/services/account.service';
import { JournalService } from '@finances/services/journal.service';
import { AccountType } from '@finances/models/account.model';

@Component({
  selector: 'app-account-edit-dialog',
  templateUrl: './account-edit-dialog.component.html',
  styleUrl: './account-edit-dialog.component.scss',
  imports: [FormsModule],
})
export class AccountEditDialogComponent {
  private accountService = inject(AccountService);
  private journalService = inject(JournalService);

  /** Account ID for editing — absent means create mode */
  accountId = input<string>();

  dialogClose = output<void>();
  dialogSave = output<void>();

  dialog = viewChild<ElementRef<HTMLDialogElement>>('dialog');
  nameInput = viewChild<ElementRef<HTMLInputElement>>('nameInput');

  isEditMode = computed(() => !!this.accountId());

  // Form fields
  accName = signal('');
  description = signal('');
  typeId = signal('');
  journalId = signal('');
  retearnId = signal('');

  // State
  loading = signal(false);
  saving = signal(false);
  errorMessage = signal<string | null>(null);

  // Reference data
  accountTypes = this.accountService.accountTypes;
  journals = this.journalService.journals;
  accounts = this.accountService.accounts;

  /** Selected account type object */
  selectedType = computed<AccountType | undefined>(() => {
    const id = this.typeId();
    return this.accountTypes().find((t) => t.id === id);
  });

  /** Whether retained earnings field should be visible */
  showRetainedEarnings = computed(() => {
    const type = this.selectedType();
    return type ? !type.balance_sheet : false;
  });

  /** Balance sheet accounts for the retained earnings dropdown */
  balanceSheetAccounts = computed(() => {
    const types = this.accountTypes();
    const bsTypeIds = new Set(types.filter((t) => t.balance_sheet).map((t) => t.id));
    return this.accounts().filter((a) => bsTypeIds.has(a.account_type.id));
  });

  /** Form validation */
  isValid = computed(() => {
    if (this.accName().trim().length < 3) return false;
    if (!this.typeId()) return false;
    if (!this.journalId()) return false;
    if (this.showRetainedEarnings() && !this.retearnId()) return false;
    return true;
  });

  constructor() {
    effect(() => {
      const id = this.accountId();
      if (id) {
        this.loadAccount(id);
      }
    });

    afterNextRender(() => {
      this.dialog()?.nativeElement.showModal();
      if (!this.accountId()) {
        this.nameInput()?.nativeElement.focus();
      }
    });
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.ctrlKey && event.key === 's') {
      event.preventDefault();
      this.onSave();
    }
  }

  private loadAccount(id: string): void {
    this.loading.set(true);
    this.errorMessage.set(null);

    this.accountService.getById(id).subscribe({
      next: (response) => {
        const acct = response.data;
        this.accName.set(acct.acc_name);
        this.description.set(acct.description || '');
        this.typeId.set(acct.account_type.id);
        this.journalId.set(acct.journal.id);
        this.retearnId.set(acct.retained_earnings?.id || '');
        this.loading.set(false);
        afterNextRender(() => {
          this.nameInput()?.nativeElement.focus();
        });
      },
      error: (err) => {
        this.loading.set(false);
        this.errorMessage.set(err.message || 'Failed to load account');
      },
    });
  }

  close(): void {
    this.dialog()?.nativeElement.close();
  }

  onSave(): void {
    if (!this.isValid() || this.saving()) return;

    this.saving.set(true);
    this.errorMessage.set(null);

    const id = this.accountId();
    const retearnValue = this.showRetainedEarnings() ? this.retearnId() : null;

    const request$ = id
      ? this.accountService.update(id, {
          acc_name: this.accName().trim(),
          description: this.description().trim() || null,
          type_id: this.typeId(),
          journal_id: this.journalId(),
          retearn_id: retearnValue || '',
        })
      : this.accountService.create({
          acc_name: this.accName().trim(),
          type_id: this.typeId(),
          journal_id: this.journalId(),
          description: this.description().trim() || null,
          retearn_id: retearnValue || null,
        });

    request$.subscribe({
      next: () => {
        this.saving.set(false);
        this.dialogSave.emit();
        this.close();
      },
      error: (err) => {
        this.saving.set(false);
        this.errorMessage.set(err.message || 'Failed to save account');
      },
    });
  }

  onCancel(): void {
    this.close();
  }
}
