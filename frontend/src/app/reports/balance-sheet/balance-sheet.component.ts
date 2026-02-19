import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { CurrencyPipe } from '@angular/common';
import { Subject, switchMap, startWith, filter } from 'rxjs';
import { ReportService } from '../report.service';
import { AccountTypeGroup, BalanceSheetRow } from '../report.models';
import { AccountSidebarComponent } from '../account-sidebar/account-sidebar.component';
import { TransactionEntryComponent } from '../../finances/transactions/transaction-entry/transaction-entry.component';

@Component({
  selector: 'app-balance-sheet',
  templateUrl: './balance-sheet.component.html',
  styleUrl: './balance-sheet.component.scss',
  imports: [RouterLink, CurrencyPipe, AccountSidebarComponent, TransactionEntryComponent],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class BalanceSheetComponent {
  private reportService = inject(ReportService);

  selectedAccountId = signal<string | null>(null);
  editTransactionId = signal<string | undefined>(undefined);
  showEntryDialog = signal(false);
  reportDate = signal(new Date().toISOString().slice(0, 10));
  private generate$ = new Subject<string>();

  private response = toSignal(
    this.generate$.pipe(
      startWith(this.reportDate()),
      filter((d) => d.length === 10),
      switchMap((d) => this.reportService.currentBalanceAccounts(d)),
    ),
  );

  groups = computed<AccountTypeGroup[]>(() => {
    const resp = this.response();
    if (!resp) return [];
    return this.groupRows(resp.data);
  });

  totalAssets = computed(() => {
    return this.groups()
      .filter((g) => g.debit_account)
      .reduce((sum, g) => sum + g.subtotal, 0);
  });

  totalLiabilitiesEquity = computed(() => {
    return this.groups()
      .filter((g) => !g.debit_account)
      .reduce((sum, g) => sum + g.subtotal, 0);
  });

  selectAccount(id: string): void {
    this.selectedAccountId.set(
      this.selectedAccountId() === id ? null : id
    );
  }

  closeSidebar(): void {
    this.selectedAccountId.set(null);
  }

  openTransaction(id: string): void {
    this.editTransactionId.set(id);
    this.showEntryDialog.set(true);
  }

  closeEntryDialog(): void {
    this.showEntryDialog.set(false);
    this.editTransactionId.set(undefined);
  }

  onDateChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.reportDate.set(input.value);
  }

  generate(): void {
    this.generate$.next(this.reportDate());
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      this.generate();
    }
  }

  private groupRows(rows: BalanceSheetRow[]): AccountTypeGroup[] {
    const map = new Map<string, AccountTypeGroup>();
    for (const row of rows) {
      let group = map.get(row.atype_id);
      if (!group) {
        group = {
          atype_id: row.atype_id,
          atype_name: row.atype_name,
          debit_account: row.debit_account,
          accounts: [],
          subtotal: 0,
        };
        map.set(row.atype_id, group);
      }
      group.accounts.push(row);
      group.subtotal += row.balance ?? 0;
    }
    return Array.from(map.values());
  }
}
