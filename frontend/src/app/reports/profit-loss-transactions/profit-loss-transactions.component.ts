import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { Subject, switchMap, startWith, filter } from 'rxjs';
import { ReportService } from '../report.service';
import { ProfitLossTransactionGroup, ProfitLossTransactionRow } from '../report.models';
import { TransactionEntryComponent } from '../../finances/transactions/transaction-entry/transaction-entry.component';

interface DateRange {
  d1: string;
  d2: string;
}

@Component({
  selector: 'app-profit-loss-transactions',
  templateUrl: './profit-loss-transactions.component.html',
  styleUrl: './profit-loss-transactions.component.scss',
  imports: [RouterLink, CurrencyPipe, DatePipe, TransactionEntryComponent],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class ProfitLossTransactionsComponent {
  private reportService = inject(ReportService);

  filtersOpen = signal(false);
  editTransactionId = signal<string | undefined>(undefined);
  showEntryDialog = signal(false);
  private today = new Date().toISOString().slice(0, 10);
  private yearStart = this.today.slice(0, 4) + '-01-01';

  startDate = signal(this.yearStart);
  endDate = signal(this.today);
  private generate$ = new Subject<DateRange>();

  private response = toSignal(
    this.generate$.pipe(
      startWith({ d1: this.yearStart, d2: this.today }),
      filter((r) => r.d1.length === 10 && r.d2.length === 10),
      switchMap((r) => this.reportService.profitLossTransactions(r.d1, r.d2)),
    ),
  );

  groups = computed<ProfitLossTransactionGroup[]>(() => {
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

  openTransaction(id: string): void {
    this.editTransactionId.set(id);
    this.showEntryDialog.set(true);
  }

  closeEntryDialog(): void {
    this.showEntryDialog.set(false);
    this.editTransactionId.set(undefined);
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

  private groupRows(rows: ProfitLossTransactionRow[]): ProfitLossTransactionGroup[] {
    const map = new Map<string, ProfitLossTransactionGroup>();
    for (const row of rows) {
      let group = map.get(row.atype_id);
      if (!group) {
        group = {
          atype_id: row.atype_id,
          atype_name: row.atype_name,
          debit_account: row.debit_account,
          rows: [],
          subtotal: 0,
        };
        map.set(row.atype_id, group);
      }
      group.rows.push(row);
      group.subtotal += row.amount ?? 0;
    }
    return Array.from(map.values());
  }
}
