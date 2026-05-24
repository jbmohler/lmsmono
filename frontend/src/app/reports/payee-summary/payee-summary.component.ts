import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { CurrencyPipe, KeyValuePipe } from '@angular/common';
import { Subject, switchMap, filter } from 'rxjs';
import { AccountService } from '@finances/services/account.service';
import { ReportService } from '../report.service';
import { PayeeSummaryRow } from '../report.models';

interface GenerateParams {
  accountId: string;
  date1: string;
  date2: string;
}

@Component({
  selector: 'app-payee-summary',
  templateUrl: './payee-summary.component.html',
  styleUrl: './payee-summary.component.scss',
  imports: [RouterLink, CurrencyPipe, KeyValuePipe],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class PayeeSummaryComponent {
  private reportService = inject(ReportService);
  private accountService = inject(AccountService);

  filtersOpen = signal(false);

  private lastMonthEnd = (() => {
    const d = new Date();
    d.setDate(0);
    return d.toISOString().slice(0, 10);
  })();
  private lastMonthStart = (() => {
    const d = new Date();
    d.setDate(0);
    d.setDate(1);
    return d.toISOString().slice(0, 10);
  })();

  selectedAccountId = signal('');
  date1 = signal(this.lastMonthStart);
  date2 = signal(this.lastMonthEnd);

  private generate$ = new Subject<GenerateParams>();

  private response = toSignal(
    this.generate$.pipe(
      filter((p) => p.accountId.length > 0),
      switchMap((p) => this.reportService.paySummary(p.accountId, p.date1, p.date2)),
    ),
  );

  rows = computed<PayeeSummaryRow[]>(() => this.response()?.data ?? []);
  accountName = computed(() => this.response()?.account_name ?? '');
  total = computed(() => this.rows().reduce((sum, r) => sum + r.debit, 0));

  accountsByType = this.accountService.accountsByType;

  onAccountChange(event: Event): void {
    this.selectedAccountId.set((event.target as HTMLSelectElement).value);
  }

  onDate1Change(event: Event): void {
    this.date1.set((event.target as HTMLInputElement).value);
  }

  onDate2Change(event: Event): void {
    this.date2.set((event.target as HTMLInputElement).value);
  }

  generate(): void {
    const accountId = this.selectedAccountId();
    if (!accountId) return;
    this.generate$.next({ accountId, date1: this.date1(), date2: this.date2() });
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      this.generate();
    }
  }
}
