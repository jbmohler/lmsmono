import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { CurrencyPipe } from '@angular/common';
import { Subject, switchMap, startWith, filter } from 'rxjs';
import { ReportService } from '../report.service';
import { AccountTypeGroup, ProfitLossRow } from '../report.models';
import { AccountSidebarComponent } from '../account-sidebar/account-sidebar.component';
import { TransactionEntryComponent } from '../../finances/transactions/transaction-entry/transaction-entry.component';
import { AccountEditDialogComponent } from '../../finances/setup/account-edit-dialog/account-edit-dialog.component';

interface DateRange {
  d1: string;
  d2: string;
}

@Component({
  selector: 'app-profit-loss',
  templateUrl: './profit-loss.component.html',
  styleUrl: './profit-loss.component.scss',
  imports: [RouterLink, CurrencyPipe, AccountSidebarComponent, TransactionEntryComponent, AccountEditDialogComponent],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class ProfitLossComponent {
  private reportService = inject(ReportService);

  filtersOpen = signal(false);
  mobileShowDetail = signal(false);
  selectedAccountId = signal<string | null>(null);
  editTransactionId = signal<string | undefined>(undefined);
  showEntryDialog = signal(false);
  showAccountEditDialog = signal(false);
  editAccountId = signal<string | undefined>(undefined);
  private today = new Date().toISOString().slice(0, 10);
  private yearStart = this.today.slice(0, 4) + '-01-01';

  startDate = signal(this.yearStart);
  endDate = signal(this.today);
  private generate$ = new Subject<DateRange>();

  private response = toSignal(
    this.generate$.pipe(
      startWith({ d1: this.yearStart, d2: this.today }),
      filter((r) => r.d1.length === 10 && r.d2.length === 10),
      switchMap((r) => this.reportService.profitAndLoss(r.d1, r.d2)),
    ),
  );

  groups = computed<AccountTypeGroup<ProfitLossRow>[]>(() => {
    const resp = this.response();
    if (!resp) return [];
    return this.groupRows(resp.data);
  });

  totalIncome = computed(() => {
    return this.groups()
      .filter((g) => !g.debit_account)
      .reduce((sum, g) => sum + g.subtotal, 0);
  });

  totalExpenses = computed(() => {
    return this.groups()
      .filter((g) => g.debit_account)
      .reduce((sum, g) => sum + g.subtotal, 0);
  });

  netIncome = computed(() => this.totalIncome() - this.totalExpenses());

  selectAccount(id: string): void {
    this.selectedAccountId.set(
      this.selectedAccountId() === id ? null : id
    );
    if (this.selectedAccountId()) {
      this.mobileShowDetail.set(true);
    }
  }

  closeSidebar(): void {
    this.selectedAccountId.set(null);
    this.mobileShowDetail.set(false);
  }

  openTransaction(id: string): void {
    this.editTransactionId.set(id);
    this.showEntryDialog.set(true);
  }

  closeEntryDialog(): void {
    this.showEntryDialog.set(false);
    this.editTransactionId.set(undefined);
  }

  openAccountEdit(id: string): void {
    this.editAccountId.set(id);
    this.showAccountEditDialog.set(true);
  }

  closeAccountEditDialog(): void {
    this.showAccountEditDialog.set(false);
    this.editAccountId.set(undefined);
  }

  onAccountSaved(): void {
    this.closeAccountEditDialog();
    this.generate();
  }

  onStartDateChange(event: Event): void {
    this.startDate.set((event.target as HTMLInputElement).value);
  }

  onEndDateChange(event: Event): void {
    this.endDate.set((event.target as HTMLInputElement).value);
  }

  generate(): void {
    this.generate$.next({ d1: this.startDate(), d2: this.endDate() });
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      this.generate();
    }
  }

  private groupRows(rows: ProfitLossRow[]): AccountTypeGroup<ProfitLossRow>[] {
    const map = new Map<string, AccountTypeGroup<ProfitLossRow>>();
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
      group.subtotal += row.amount ?? 0;
    }
    return Array.from(map.values());
  }
}
