import { Component, computed, signal } from '@angular/core';
import { TransactionEntryComponent } from '../transactions/transaction-entry/transaction-entry.component';

interface Transaction {
  id: string;
  date: string; // YYYY-MM-DD
  payee: string;
  amount: number;
}

interface CalendarDay {
  day: number | null;
  date: string | null;
  isCurrentMonth: boolean;
  transactions: Transaction[];
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
  weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  currentYear = signal(2026);
  currentMonth = signal(0); // 0 = January

  // Transaction entry dialog state
  showEntryDialog = signal(false);
  entryDate = signal<string | undefined>(undefined);

  monthName = computed(() => {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return `${months[this.currentMonth()]} ${this.currentYear()}`;
  });

  // Mock transaction data
  private transactions: Transaction[] = [
    { id: '1', date: '2026-01-03', payee: 'Whole Foods Market', amount: -127.43 },
    { id: '2', date: '2026-01-03', payee: 'Shell Gas Station', amount: -45.00 },
    { id: '3', date: '2026-01-07', payee: 'Payroll Deposit', amount: 3250.00 },
    { id: '4', date: '2026-01-10', payee: 'Netflix', amount: -15.99 },
    { id: '5', date: '2026-01-10', payee: 'Spotify', amount: -9.99 },
    { id: '6', date: '2026-01-12', payee: 'Target', amount: -89.23 },
    { id: '7', date: '2026-01-15', payee: 'Electric Company', amount: -142.50 },
    { id: '8', date: '2026-01-15', payee: 'Water Utility', amount: -38.00 },
    { id: '9', date: '2026-01-18', payee: 'Amazon', amount: -67.99 },
    { id: '10', date: '2026-01-21', payee: 'Payroll Deposit', amount: 3250.00 },
    { id: '11', date: '2026-01-22', payee: 'Costco', amount: -234.56 },
    { id: '12', date: '2026-01-25', payee: 'Rent Payment', amount: -1800.00 },
    { id: '13', date: '2026-01-28', payee: 'Dentist', amount: -150.00 },
    { id: '14', date: '2026-01-31', payee: 'Internet Provider', amount: -79.99 },
    // February transactions
    { id: '15', date: '2026-02-05', payee: 'Whole Foods Market', amount: -98.32 },
    { id: '16', date: '2026-02-07', payee: 'Payroll Deposit', amount: 3250.00 },
    { id: '17', date: '2026-02-14', payee: 'Restaurant - Valentines', amount: -185.00 },
    { id: '18', date: '2026-02-21', payee: 'Payroll Deposit', amount: 3250.00 },
    { id: '19', date: '2026-02-25', payee: 'Rent Payment', amount: -1800.00 },
    // December 2025 transactions (for prev month nav)
    { id: '20', date: '2025-12-15', payee: 'Holiday Shopping', amount: -450.00 },
    { id: '21', date: '2025-12-24', payee: 'Gift Cards', amount: -200.00 },
    { id: '22', date: '2025-12-31', payee: 'New Years Eve', amount: -125.00 },
  ];

  calendarDays = computed<CalendarDay[]>(() => {
    const year = this.currentYear();
    const month = this.currentMonth();

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
        transactions: this.getTransactionsForDate(dateStr),
      });
    }

    // Current month days
    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = this.formatDate(year, month, day);
      days.push({
        day,
        date: dateStr,
        isCurrentMonth: true,
        transactions: this.getTransactionsForDate(dateStr),
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
        transactions: this.getTransactionsForDate(dateStr),
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

  openEntryDialog(date?: string): void {
    this.entryDate.set(date);
    this.showEntryDialog.set(true);
  }

  closeEntryDialog(): void {
    this.showEntryDialog.set(false);
    this.entryDate.set(undefined);
  }

  onDayClick(day: CalendarDay): void {
    if (day.date) {
      this.openEntryDialog(day.date);
    }
  }

  onTransactionSaved(): void {
    // TODO: Refresh calendar when API is connected
    console.log('Transaction saved');
  }

  private formatDate(year: number, month: number, day: number): string {
    const m = (month + 1).toString().padStart(2, '0');
    const d = day.toString().padStart(2, '0');
    return `${year}-${m}-${d}`;
  }

  private getTransactionsForDate(date: string): Transaction[] {
    return this.transactions.filter(t => t.date === date);
  }

  trackByDate(_index: number, day: CalendarDay): string | null {
    return day.date;
  }

  trackByDay(_index: number, day: string): string {
    return day;
  }
}
