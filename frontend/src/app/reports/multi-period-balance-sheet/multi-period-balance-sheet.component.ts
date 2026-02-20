import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { CurrencyPipe } from '@angular/common';
import { Subject, switchMap, startWith, filter } from 'rxjs';
import { ReportService } from '../report.service';
import {
  MultiPeriodAccountTypeGroup,
  MultiPeriodBalanceSheetRow,
} from '../report.models';
import { AccountSidebarComponent } from '../account-sidebar/account-sidebar.component';
import { TransactionEntryComponent } from '../../finances/transactions/transaction-entry/transaction-entry.component';
import { AccountEditDialogComponent } from '../../finances/setup/account-edit-dialog/account-edit-dialog.component';

interface GenerateParams {
  year: number;
  month: number;
  periods: number;
}

@Component({
  selector: 'app-multi-period-balance-sheet',
  templateUrl: './multi-period-balance-sheet.component.html',
  styleUrl: './multi-period-balance-sheet.component.scss',
  imports: [RouterLink, CurrencyPipe, AccountSidebarComponent, TransactionEntryComponent, AccountEditDialogComponent],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class MultiPeriodBalanceSheetComponent {
  private reportService = inject(ReportService);

  selectedAccountId = signal<string | null>(null);
  editTransactionId = signal<string | undefined>(undefined);
  showEntryDialog = signal(false);
  showAccountEditDialog = signal(false);
  editAccountId = signal<string | undefined>(undefined);

  private now = new Date();
  reportYear = signal(this.now.getFullYear());
  reportMonth = signal(this.now.getMonth() + 1);
  reportPeriods = signal(5);

  private generate$ = new Subject<GenerateParams>();

  private response = toSignal(
    this.generate$.pipe(
      startWith({
        year: this.reportYear(),
        month: this.reportMonth(),
        periods: this.reportPeriods(),
      }),
      filter((p) => p.year > 0 && p.month >= 1 && p.month <= 12 && p.periods >= 1),
      switchMap((p) => this.reportService.multiPeriodBalanceSheet(p.year, p.month, p.periods)),
    ),
  );

  periods = computed(() => this.response()?.periods ?? []);

  groups = computed<MultiPeriodAccountTypeGroup[]>(() => {
    const resp = this.response();
    if (!resp) return [];
    return this.groupRows(resp.data, resp.periods.length);
  });

  assetGroups = computed(() => this.groups().filter((g) => g.debit_account));
  liabilityEquityGroups = computed(() => this.groups().filter((g) => !g.debit_account));

  totalAssets = computed(() => this.sumGroupTotals(this.assetGroups()));
  totalLiabilitiesEquity = computed(() => this.sumGroupTotals(this.liabilityEquityGroups()));

  selectAccount(id: string): void {
    this.selectedAccountId.set(this.selectedAccountId() === id ? null : id);
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

  onYearChange(event: Event): void {
    this.reportYear.set(+(event.target as HTMLInputElement).value);
  }

  onMonthChange(event: Event): void {
    this.reportMonth.set(+(event.target as HTMLSelectElement).value);
  }

  onPeriodsChange(event: Event): void {
    this.reportPeriods.set(+(event.target as HTMLInputElement).value);
  }

  generate(): void {
    this.generate$.next({
      year: this.reportYear(),
      month: this.reportMonth(),
      periods: this.reportPeriods(),
    });
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      this.generate();
    }
    if (event.key === 'Escape') {
      this.closeSidebar();
    }
  }

  formatPeriodHeader(dateStr: string): string {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  }

  private groupRows(rows: MultiPeriodBalanceSheetRow[], periodCount: number): MultiPeriodAccountTypeGroup[] {
    const map = new Map<string, MultiPeriodAccountTypeGroup>();
    for (const row of rows) {
      let group = map.get(row.atype_id);
      if (!group) {
        group = {
          atype_id: row.atype_id,
          atype_name: row.atype_name,
          debit_account: row.debit_account,
          accounts: [],
          subtotals: new Array(periodCount).fill(0),
        };
        map.set(row.atype_id, group);
      }
      group.accounts.push(row);
      for (let i = 0; i < periodCount; i++) {
        group.subtotals[i] += row.balances[i] ?? 0;
      }
    }
    return Array.from(map.values());
  }

  private sumGroupTotals(groups: MultiPeriodAccountTypeGroup[]): number[] {
    if (groups.length === 0) return [];
    const periodCount = groups[0].subtotals.length;
    const totals = new Array(periodCount).fill(0);
    for (const g of groups) {
      for (let i = 0; i < periodCount; i++) {
        totals[i] += g.subtotals[i];
      }
    }
    return totals;
  }
}
