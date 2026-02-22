import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { CurrencyPipe, DatePipe, KeyValuePipe } from '@angular/common';
import { Subject, switchMap, filter } from 'rxjs';
import { AccountService } from '@finances/services/account.service';
import { ReportService } from '../report.service';
import { AccountRunningBalanceRow } from '../report.models';
import { TransactionEntryComponent } from '../../finances/transactions/transaction-entry/transaction-entry.component';

interface GenerateParams {
  accountId: string;
  d: string;
}

@Component({
  selector: 'app-account-running-balance',
  templateUrl: './account-running-balance.component.html',
  styleUrl: './account-running-balance.component.scss',
  imports: [RouterLink, CurrencyPipe, DatePipe, KeyValuePipe, TransactionEntryComponent],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class AccountRunningBalanceComponent {
  private reportService = inject(ReportService);
  private accountService = inject(AccountService);

  filtersOpen = signal(false);
  editTransactionId = signal<string | undefined>(undefined);
  newTransactionDate = signal<string | undefined>(undefined);
  newTransactionTemplate = signal<{ payee: string | null; memo: string | null } | undefined>(undefined);
  showEntryDialog = signal(false);

  private today = new Date().toISOString().slice(0, 10);
  private yearStart = this.today.slice(0, 4) + '-01-01';

  selectedAccountId = signal('');
  startDate = signal(this.yearStart);

  private generate$ = new Subject<GenerateParams>();

  private response = toSignal(
    this.generate$.pipe(
      filter((p) => p.accountId.length > 0 && p.d.length === 10),
      switchMap((p) => this.reportService.accountRunningBalance(p.accountId, p.d)),
    ),
  );

  rows = computed<AccountRunningBalanceRow[]>(() => this.response()?.data ?? []);

  // Account types with balance_sheet flag for filtering
  private accountTypes = this.accountService.accountTypes;

  // Balance sheet account type IDs
  private balanceSheetTypeIds = computed(() =>
    new Set(this.accountTypes().filter((t) => t.balance_sheet).map((t) => t.id)),
  );

  // All accounts grouped by type name, filtered to balance sheet only
  balanceSheetAccountsByType = computed(() => {
    const bsIds = this.balanceSheetTypeIds();
    const accounts = this.accountService.accounts();
    const grouped = new Map<string, typeof accounts>();
    for (const account of accounts) {
      if (!bsIds.has(account.account_type.id)) continue;
      const typeName = account.account_type.name;
      const group = grouped.get(typeName) ?? [];
      group.push(account);
      grouped.set(typeName, group);
    }
    return grouped;
  });

  onAccountChange(event: Event): void {
    this.selectedAccountId.set((event.target as HTMLSelectElement).value);
  }

  onStartDateChange(event: Event): void {
    this.startDate.set((event.target as HTMLInputElement).value);
  }

  generate(): void {
    const accountId = this.selectedAccountId();
    const d = this.startDate();
    if (!accountId) return;
    this.generate$.next({ accountId, d });
  }

  openRecorded(id: string): void {
    this.editTransactionId.set(id);
    this.newTransactionDate.set(undefined);
    this.showEntryDialog.set(true);
  }

  openSpeculative(row: AccountRunningBalanceRow): void {
    this.editTransactionId.set(undefined);
    this.newTransactionDate.set(row.trandate);
    this.newTransactionTemplate.set({ payee: row.payee, memo: row.memo });
    this.showEntryDialog.set(true);
  }

  closeEntryDialog(): void {
    this.showEntryDialog.set(false);
    this.editTransactionId.set(undefined);
    this.newTransactionDate.set(undefined);
    this.newTransactionTemplate.set(undefined);
  }

  onDialogSave(): void {
    this.closeEntryDialog();
    this.generate();
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      this.generate();
    }
  }

  isInitialBalance(row: AccountRunningBalanceRow): boolean {
    return row.payee === 'Initial Balance' && row.tid === null && !row.is_speculative;
  }
}
