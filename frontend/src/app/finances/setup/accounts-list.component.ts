import { Component, inject, signal } from '@angular/core';
import { AccountService } from '../services/account.service';
import { AccountEditDialogComponent } from './account-edit-dialog/account-edit-dialog.component';

@Component({
  selector: 'app-accounts-list',
  templateUrl: './accounts-list.component.html',
  styleUrl: './accounts-list.component.scss',
  imports: [AccountEditDialogComponent],
})
export class AccountsListComponent {
  private service = inject(AccountService);

  accounts = this.service.accounts;
  columns = this.service.columns;

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
