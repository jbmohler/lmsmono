import { Component, computed, effect, inject, signal, ChangeDetectionStrategy } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { CurrencyPipe } from '@angular/common';
import { Subject, of, switchMap, startWith, filter, map, catchError } from 'rxjs';
import { MultiRowResponse } from '@core/api/api.types';
import { PageTitleService } from '@core/page-title.service';
import { ReportService } from '../report.service';
import {
  MultiPeriodProfitLossGroup,
  ProfitLossPeriod,
  ProfitLossRow,
} from '../report.models';
import { AccountSidebarComponent } from '../account-sidebar/account-sidebar.component';
import { TransactionEntryComponent } from '../../finances/transactions/transaction-entry/transaction-entry.component';
import { AccountEditDialogComponent } from '../../finances/setup/account-edit-dialog/account-edit-dialog.component';

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

interface GenerateParams {
  endYear: number;
  endMonth: number;
  monthsPerPeriod: number;
  periodCount: number;
}

function pad(n: number): string {
  return n.toString().padStart(2, '0');
}

/** Last calendar day of a 1-based month. */
function lastDayOfMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** Step a 1-based year/month back by n months. */
function monthsBack(year: number, month: number, n: number): { year: number; month: number } {
  const zeroBased = year * 12 + (month - 1) - n;
  return { year: Math.floor(zeroBased / 12), month: (zeroBased % 12) + 1 };
}

/**
 * Rolling windows of `monthsPerPeriod` months, the newest ending on the last
 * day of the anchor month and each earlier one stepping back a full period.
 * Mirrors _rolling_half_periods() in cli/lms.py, generalised past 6 months.
 */
function buildProfitLossPeriods(
  endYear: number,
  endMonth: number,
  monthsPerPeriod: number,
  periodCount: number,
): ProfitLossPeriod[] {
  const periods: ProfitLossPeriod[] = [];
  let year = endYear;
  let month = endMonth;

  for (let i = 0; i < periodCount; i++) {
    const d2 = `${year}-${pad(month)}-${pad(lastDayOfMonth(year, month))}`;
    const start = monthsBack(year, month, monthsPerPeriod - 1);
    const d1 = `${start.year}-${pad(start.month)}-01`;

    periods.push({ label: `${MONTH_ABBR[month - 1]} ${year}`, d1, d2 });

    ({ year, month } = monthsBack(year, month, monthsPerPeriod));
  }

  return periods;
}

@Component({
  selector: 'app-multi-period-profit-loss',
  templateUrl: './multi-period-profit-loss.component.html',
  styleUrl: './multi-period-profit-loss.component.scss',
  imports: [RouterLink, CurrencyPipe, AccountSidebarComponent, TransactionEntryComponent, AccountEditDialogComponent],
  changeDetection: ChangeDetectionStrategy.Eager,
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class MultiPeriodProfitLossComponent {
  private reportService = inject(ReportService);
  private pageTitle = inject(PageTitleService);

  selectedAccountId = signal<string | null>(null);
  editTransactionId = signal<string | undefined>(undefined);
  showEntryDialog = signal(false);
  showAccountEditDialog = signal(false);
  editAccountId = signal<string | undefined>(undefined);

  // Defaults: the month that just ended, four rolling 6-month windows.
  private priorMonthEnd = new Date(new Date().getFullYear(), new Date().getMonth(), 0);
  endYear = signal(this.priorMonthEnd.getFullYear());
  endMonth = signal(this.priorMonthEnd.getMonth() + 1);
  monthsPerPeriod = signal(6);
  periodCount = signal(4);

  loadError = signal<string | null>(null);

  private generate$ = new Subject<GenerateParams>();

  private response = toSignal(
    this.generate$.pipe(
      startWith({
        endYear: this.endYear(),
        endMonth: this.endMonth(),
        monthsPerPeriod: this.monthsPerPeriod(),
        periodCount: this.periodCount(),
      }),
      filter(
        p =>
          p.endYear > 0 &&
          p.endMonth >= 1 &&
          p.endMonth <= 12 &&
          p.monthsPerPeriod >= 1 &&
          p.periodCount >= 1,
      ),
      switchMap(p => {
        const periods = buildProfitLossPeriods(
          p.endYear,
          p.endMonth,
          p.monthsPerPeriod,
          p.periodCount,
        );
        this.loadError.set(null);
        return this.reportService.multiPeriodProfitLoss(periods).pipe(
          map(responses => ({
            periods,
            groups: this.pivot(responses),
            monthsPerPeriod: p.monthsPerPeriod,
          })),
          // Swallow the error so the stream survives for the next Generate;
          // report nothing rather than a partial set of columns.
          catchError(() => {
            this.loadError.set('Could not load every period — no columns are shown, since a partial set would be misleading.');
            return of({ periods: [], groups: [], monthsPerPeriod: p.monthsPerPeriod });
          }),
        );
      }),
    ),
  );

  periods = computed<ProfitLossPeriod[]>(() => this.response()?.periods ?? []);
  groups = computed<MultiPeriodProfitLossGroup[]>(() => this.response()?.groups ?? []);

  /** Caption above the column headers, e.g. "For the 6 months ending:". */
  periodCaption = computed(() => {
    const months = this.response()?.monthsPerPeriod ?? 0;
    return months === 1 ? 'For the month ending:' : `For the ${months} months ending:`;
  });

  incomeGroups = computed(() => this.groups().filter(g => !g.debit_account));
  expenseGroups = computed(() => this.groups().filter(g => g.debit_account));

  totalIncome = computed(() => this.sumSubtotals(this.incomeGroups()));
  totalExpenses = computed(() => this.sumSubtotals(this.expenseGroups()));

  netIncome = computed(() => {
    const income = this.totalIncome();
    const expenses = this.totalExpenses();
    return this.periods().map((_, i) => (income[i] ?? 0) - (expenses[i] ?? 0));
  });

  // Periods are newest-first (see buildProfitLossPeriods) — periods()[0] is
  // the anchor month the rolling windows are counted back from.
  anchorPeriodLabel = computed(() => this.periods()[0]?.label ?? '');

  constructor() {
    effect(() => {
      this.pageTitle.setDetail(this.anchorPeriodLabel() || null);
    });
  }

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

  onEndMonthChange(event: Event): void {
    this.endMonth.set(+(event.target as HTMLSelectElement).value);
  }

  onEndYearChange(event: Event): void {
    this.endYear.set(+(event.target as HTMLInputElement).value);
  }

  onMonthsPerPeriodChange(event: Event): void {
    this.monthsPerPeriod.set(+(event.target as HTMLInputElement).value);
  }

  onPeriodCountChange(event: Event): void {
    this.periodCount.set(+(event.target as HTMLInputElement).value);
  }

  generate(): void {
    this.generate$.next({
      endYear: this.endYear(),
      endMonth: this.endMonth(),
      monthsPerPeriod: this.monthsPerPeriod(),
      periodCount: this.periodCount(),
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

  /**
   * Fold one response per period into one row per account with an amount per
   * period, ordered by account type, journal, then account name — the same
   * shape _write_profit_loss_xlsx() builds in cli/lms.py.
   */
  private pivot(responses: MultiRowResponse<ProfitLossRow>[]): MultiPeriodProfitLossGroup[] {
    const periodCount = responses.length;
    const byAccount = new Map<string, { meta: ProfitLossRow; amounts: number[] }>();

    responses.forEach((response, index) => {
      for (const row of response.data) {
        let entry = byAccount.get(row.id);
        if (!entry) {
          entry = { meta: row, amounts: new Array<number>(periodCount).fill(0) };
          byAccount.set(row.id, entry);
        }
        entry.amounts[index] = row.amount ?? 0;
      }
    });

    // Matches the ORDER BY the API applies, since merging periods loses row order
    const ordered = [...byAccount.values()].sort(
      (a, b) =>
        a.meta.atype_sort - b.meta.atype_sort ||
        a.meta.atype_id.localeCompare(b.meta.atype_id) ||
        a.meta.journal.name.localeCompare(b.meta.journal.name) ||
        a.meta.acc_name.localeCompare(b.meta.acc_name),
    );

    const groups: MultiPeriodProfitLossGroup[] = [];
    for (const { meta, amounts } of ordered) {
      let group = groups[groups.length - 1];
      if (!group || group.atype_id !== meta.atype_id) {
        group = {
          atype_id: meta.atype_id,
          atype_name: meta.atype_name,
          atype_sort: meta.atype_sort,
          debit_account: meta.debit_account,
          accounts: [],
          subtotals: new Array<number>(periodCount).fill(0),
        };
        groups.push(group);
      }
      group.accounts.push({
        id: meta.id,
        acc_name: meta.acc_name,
        description: meta.description,
        journal: meta.journal,
        amounts,
      });
      for (let i = 0; i < periodCount; i++) {
        group.subtotals[i] += amounts[i];
      }
    }

    return groups;
  }

  private sumSubtotals(groups: MultiPeriodProfitLossGroup[]): number[] {
    const totals = new Array<number>(this.periods().length).fill(0);
    for (const group of groups) {
      group.subtotals.forEach((value, i) => (totals[i] += value));
    }
    return totals;
  }
}
