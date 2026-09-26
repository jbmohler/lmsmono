import { LocalDate } from '@js-joda/core';
import { Component, computed, signal, inject, effect, ChangeDetectionStrategy } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { BehaviorSubject, Subject, combineLatest, merge } from 'rxjs';
import { auditTime, startWith, switchMap } from 'rxjs/operators';
import { TransactionEntryComponent } from '../transactions/transaction-entry/transaction-entry.component';
import { TransactionService } from '../services/transaction.service';
import { ChangeNotificationService } from '@core/events/change-notification.service';
import { TransactionFilters } from '@finances/models/transaction.model';

/**
 * Collapses a local save and the notification it echoes back into one refetch,
 * and coalesces bursts of changes from other users.
 */
const REFRESH_COALESCE_MS = 150;

interface CalendarTransaction {
  id: string;
  date: string;
  payee: string;
}

interface CalendarDay {
  day: number | null;
  date: string | null;
  isCurrentMonth: boolean;
  transactions: CalendarTransaction[];
}

@Component({
  selector: 'app-transaction-calendar',
  templateUrl: './transaction-calendar.component.html',
  styleUrl: './transaction-calendar.component.scss',
  imports: [TransactionEntryComponent],
  changeDetection: ChangeDetectionStrategy.Eager,
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class TransactionCalendarComponent {
  private transactionService = inject(TransactionService);
  private changes = inject(ChangeNotificationService);

  weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  /** First day of the month being displayed. */
  viewMonth = signal(LocalDate.now().withDayOfMonth(1));

  // Transaction entry dialog state
  showEntryDialog = signal(false);
  entryDate = signal<string | undefined>(undefined);
  editTransactionId = signal<string | undefined>(undefined);

  monthName = computed(() => {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    const m = this.viewMonth();
    return `${months[m.monthValue() - 1]} ${m.year()}`;
  });

  // Local filter & refresh state
  private filters$ = new BehaviorSubject<TransactionFilters>({});
  private refresh$ = new Subject<void>();

  // Refetch on our own writes and on anyone else's, from any tab or user
  private trigger$ = merge(
    this.refresh$,
    this.changes.forEntity('transactions')
  ).pipe(auditTime(REFRESH_COALESCE_MS), startWith(undefined));

  // Local reactive data pipeline
  private listResponse = toSignal(
    combineLatest([
      this.filters$,
      this.trigger$,
    ]).pipe(
      switchMap(([filters]) => this.transactionService.list(filters))
    )
  );

  private allTransactions = computed(() => this.listResponse()?.data ?? []);

  // Map transactions by date for quick lookup
  private transactionsByDate = computed(() => {
    const map = new Map<string, CalendarTransaction[]>();
    for (const txn of this.allTransactions()) {
      const date = txn.trandate;
      if (!map.has(date)) {
        map.set(date, []);
      }
      map.get(date)!.push({
        id: txn.id,
        date: txn.trandate,
        payee: txn.payee || '(no payee)',
      });
    }
    return map;
  });

  constructor() {
    // Update filters when month changes to load relevant transactions
    effect(() => {
      const firstDay = this.viewMonth();
      const lastDay = firstDay.withDayOfMonth(firstDay.lengthOfMonth());

      // Add buffer for prev/next month days shown in calendar
      const from = firstDay.minusDays(7);
      const to = lastDay.plusDays(14);

      this.filters$.next({
        from: from.toString(),
        to: to.toString(),
      });
    });
  }

  calendarDays = computed<CalendarDay[]>(() => {
    const firstDay = this.viewMonth();
    const txnMap = this.transactionsByDate();
    const daysInMonth = firstDay.lengthOfMonth();
    // Sunday = 0
    const startDayOfWeek = firstDay.dayOfWeek().value() % 7;

    // When the 1st falls on Sun or Mon the default padding (0 or 1) leaves the
    // calendar lopsided with many trailing next-month days.  Show the full prior
    // week instead so the trailing days balance out.
    const padding = (startDayOfWeek === 0 || startDayOfWeek === 1)
      ? startDayOfWeek + 7
      : startDayOfWeek;

    const days: CalendarDay[] = [];

    // Previous month padding
    const prevMonth = firstDay.minusMonths(1);
    const daysInPrevMonth = prevMonth.lengthOfMonth();

    for (let i = padding - 1; i >= 0; i--) {
      const day = daysInPrevMonth - i;
      const dateStr = prevMonth.withDayOfMonth(day).toString();
      days.push({
        day,
        date: dateStr,
        isCurrentMonth: false,
        transactions: txnMap.get(dateStr) || [],
      });
    }

    // Current month days
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = firstDay.withDayOfMonth(day).toString();
      days.push({
        day,
        date: dateStr,
        isCurrentMonth: true,
        transactions: txnMap.get(dateStr) || [],
      });
    }

    // Next month padding to fill grid (6 rows = 42 cells)
    const nextMonth = firstDay.plusMonths(1);
    const remaining = 42 - days.length;

    for (let day = 1; day <= remaining; day++) {
      const dateStr = nextMonth.withDayOfMonth(day).toString();
      days.push({
        day,
        date: dateStr,
        isCurrentMonth: false,
        transactions: txnMap.get(dateStr) || [],
      });
    }

    return days;
  });

  handleKeydown(event: KeyboardEvent): void {
    // Ctrl+Shift+N - open new transaction dialog
    if (event.ctrlKey && event.shiftKey && event.key === 'N') {
      event.preventDefault();
      this.openEntryDialog();
    }
  }

  previousMonth(): void {
    this.viewMonth.update(m => m.minusMonths(1));
  }

  nextMonth(): void {
    this.viewMonth.update(m => m.plusMonths(1));
  }

  openEntryDialog(date?: string, transactionId?: string): void {
    this.entryDate.set(date);
    this.editTransactionId.set(transactionId);
    this.showEntryDialog.set(true);
  }

  closeEntryDialog(): void {
    this.showEntryDialog.set(false);
    this.entryDate.set(undefined);
    this.editTransactionId.set(undefined);
  }

  onDayClick(day: CalendarDay): void {
    if (day.date) {
      this.openEntryDialog(day.date);
    }
  }

  onTransactionClick(event: Event, txn: CalendarTransaction): void {
    event.stopPropagation(); // Prevent day click from firing
    this.openEntryDialog(undefined, txn.id);
  }

  onTransactionSaved(): void {
    this.refresh$.next();
  }

  trackByDate(_index: number, day: CalendarDay): string | null {
    return day.date;
  }

  trackByDay(_index: number, day: string): string {
    return day;
  }

  trackByTxnId(_index: number, txn: CalendarTransaction): string {
    return txn.id;
  }
}
