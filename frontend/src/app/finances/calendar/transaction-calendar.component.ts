import { Component } from '@angular/core';

@Component({
  selector: 'app-transaction-calendar',
  templateUrl: './transaction-calendar.component.html',
  styleUrl: './transaction-calendar.component.scss',
})
export class TransactionCalendarComponent {
  weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  calendarDays: string[] = [];

  constructor() {
    // Generate simple calendar days (placeholder)
    for (let i = 0; i < 35; i++) {
      if (i < 3) {
        this.calendarDays.push('');
      } else if (i - 3 < 31) {
        this.calendarDays.push((i - 2).toString());
      } else {
        this.calendarDays.push('');
      }
    }
  }
}
