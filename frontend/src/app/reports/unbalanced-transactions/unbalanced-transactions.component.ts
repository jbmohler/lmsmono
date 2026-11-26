import { Component, computed, inject, signal, ChangeDetectionStrategy } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { Subject, switchMap, startWith } from 'rxjs';
import { ReportService } from '../report.service';
import { UnbalancedTransactionRow } from '../report.models';
import { TransactionEntryComponent } from '../../finances/transactions/transaction-entry/transaction-entry.component';

interface JournalGroup {
  journal_id: string;
  journal_name: string;
  rows: UnbalancedTransactionRow[];
  subtotal: number;
}

/**
 * Every transaction's splits should net to zero within each journal they touch.
 * This report lists the ones that don't — it should normally be empty.
 */
@Component({
  selector: 'app-unbalanced-transactions',
  templateUrl: './unbalanced-transactions.component.html',
  styleUrl: './unbalanced-transactions.component.scss',
  imports: [RouterLink, CurrencyPipe, DatePipe, TransactionEntryComponent],
  changeDetection: ChangeDetectionStrategy.Eager,
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class UnbalancedTransactionsComponent {
  private reportService = inject(ReportService);

  editTransactionId = signal<string | undefined>(undefined);
  showEntryDialog = signal(false);
  private refresh$ = new Subject<void>();

  private response = toSignal(
    this.refresh$.pipe(
      startWith(undefined),
      switchMap(() => this.reportService.unbalancedTransactions()),
    ),
  );

  loaded = computed(() => this.response() !== undefined);

  groups = computed<JournalGroup[]>(() => {
    const map = new Map<string, JournalGroup>();
    for (const row of this.response()?.data ?? []) {
      let group = map.get(row.journal.id);
      if (!group) {
        group = { journal_id: row.journal.id, journal_name: row.journal.name, rows: [], subtotal: 0 };
        map.set(row.journal.id, group);
      }
      group.rows.push(row);
      group.subtotal = Math.round((group.subtotal + row.imbalance) * 100) / 100;
    }
    return Array.from(map.values());
  });

  openTransaction(id: string): void {
    this.editTransactionId.set(id);
    this.showEntryDialog.set(true);
  }

  closeEntryDialog(): void {
    this.showEntryDialog.set(false);
    this.editTransactionId.set(undefined);
  }

  onTransactionSaved(): void {
    this.closeEntryDialog();
    this.refresh();
  }

  refresh(): void {
    this.refresh$.next();
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      this.refresh();
    }
  }
}
