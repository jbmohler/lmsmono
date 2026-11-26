import { Component, computed, inject, signal, ChangeDetectionStrategy } from '@angular/core';
import { AccountService } from '../services/account.service';
import { JournalService } from '../services/journal.service';
import { AccountEditDialogComponent } from './account-edit-dialog/account-edit-dialog.component';

@Component({
  selector: 'app-accounts-list',
  templateUrl: './accounts-list.component.html',
  styleUrl: './accounts-list.component.scss',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [AccountEditDialogComponent],
})
export class AccountsListComponent {
  private service = inject(AccountService);
  private journalService = inject(JournalService);

  accountTypes = this.service.accountTypes;
  journals = this.journalService.journals;

  /** Selected account type / journal ids; empty string means all. */
  typeFilter = signal('');
  journalFilter = signal('');

  accounts = computed(() => {
    const typeId = this.typeFilter();
    const journalId = this.journalFilter();
    return this.service
      .accounts()
      .filter((a) => !typeId || a.account_type.id === typeId)
      .filter((a) => !journalId || a.journal.id === journalId);
  });

  /** Ids of account types that are not on the balance sheet (income/expense). */
  private plTypeIds = computed(
    () => new Set(this.accountTypes().filter((t) => !t.balance_sheet).map((t) => t.id)),
  );

  /**
   * P&L accounts must roll into a retained earnings account, or their balance
   * drops out of the balance sheet.
   */
  needsRetainedEarnings(typeId: string): boolean {
    return this.plTypeIds().has(typeId);
  }

  onTypeFilterChange(event: Event): void {
    this.typeFilter.set((event.target as HTMLSelectElement).value);
  }

  onJournalFilterChange(event: Event): void {
    this.journalFilter.set((event.target as HTMLSelectElement).value);
  }

  showEditDialog = signal(false);
  editAccountId = signal<string | undefined>(undefined);

  openCreate(): void {
    this.editAccountId.set(undefined);
    this.showEditDialog.set(true);
  }

  openEdit(accountId: string): void {
    this.editAccountId.set(accountId);
    this.showEditDialog.set(true);
  }

  onDialogClose(): void {
    this.showEditDialog.set(false);
  }

  onDialogSave(): void {
    this.showEditDialog.set(false);
    this.service.refreshAccounts();
  }
}
