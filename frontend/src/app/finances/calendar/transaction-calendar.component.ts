import { Component, computed, signal, inject, effect } from '@angular/core';
import { TransactionEntryComponent } from '../transactions/transaction-entry/transaction-entry.component';
import { TransactionService } from '../services/transaction.service';

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
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class TransactionCalendarComponent {
  private transactionService = inject(TransactionService);

  weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  currentYear = signal(new Date().getFullYear());
  currentMonth = signal(new Date().getMonth());

  // Transaction entry dialog state
  showEntryDialog = signal(false);
  entryDate = signal<string | undefined>(undefined);
  editTransactionId = signal<string | undefined>(undefined);

  monthName = computed(() => {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return `${months[this.currentMonth()]} ${this.currentYear()}`;
  });

  // Transactions from the service
  private allTransactions = this.transactionService.transactions;

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
      const year = this.currentYear();
      const month = this.currentMonth();

      // Calculate date range for visible calendar (includes padding days)
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);

      // Add buffer for prev/next month days shown in calendar
      const from = new Date(firstDay);
      from.setDate(from.getDate() - 7);
      const to = new Date(lastDay);
      to.setDate(to.getDate() + 14);

      this.transactionService.setFilters({
        from: this.formatDate(from.getFullYear(), from.getMonth(), from.getDate()),
        to: this.formatDate(to.getFullYear(), to.getMonth(), to.getDate()),
      });
    });
  }

  calendarDays = computed<CalendarDay[]>(() => {
    const year = this.currentYear();
    const month = this.currentMonth();
    const txnMap = this.transactionsByDate();

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startDayOfWeek = firstDay.getDay();

    const days: CalendarDay[] = [];

    // Previous month padding
    const prevMonth = month === 0 ? 11 : month - 1;
    const prevYear = month === 0 ? year - 1 : year;
    const daysInPrevMonth = new Date(prevYear, prevMonth + 1, 0).getDate();

    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const day = daysInPrevMonth - i;
      const dateStr = this.formatDate(prevYear, prevMonth, day);
      days.push({
        day,
        date: dateStr,
        isCurrentMonth: false,
        transactions: txnMap.get(dateStr) || [],
      });
    }

    // Current month days
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = this.formatDate(year, month, day);
      days.push({
        day,
        date: dateStr,
        isCurrentMonth: true,
        transactions: txnMap.get(dateStr) || [],
      });
    }

    // Next month padding to fill grid (6 rows = 42 cells)
    const nextMonth = month === 11 ? 0 : month + 1;
    const nextYear = month === 11 ? year + 1 : year;
    const remaining = 42 - days.length;

    for (let day = 1; day <= remaining; day++) {
      const dateStr = this.formatDate(nextYear, nextMonth, day);
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
    if (this.currentMonth() === 0) {
      this.currentMonth.set(11);
      this.currentYear.update(y => y - 1);
    } else {
      this.currentMonth.update(m => m - 1);
    }
  }

  nextMonth(): void {
    if (this.currentMonth() === 11) {
      this.currentMonth.set(0);
      this.currentYear.update(y => y + 1);
    } else {
      this.currentMonth.update(m => m + 1);
    }
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
    this.transactionService.refresh();
  }

  private formatDate(year: number, month: number, day: number): string {
    const m = (month + 1).toString().padStart(2, '0');
    const d = day.toString().padStart(2, '0');
    return `${year}-${m}-${d}`;
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
