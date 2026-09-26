import { LocalDate } from '@js-joda/core';

const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Formats a `YYYY-MM-DD` report input as e.g. "Jan 15, 2026", for display
 * (report headings, page titles) rather than for another date input. */
export function formatReportDate(dateStr: string): string {
  const d = LocalDate.parse(dateStr);
  return `${MONTH_ABBR[d.monthValue() - 1]} ${d.dayOfMonth()}, ${d.year()}`;
}

/** Formats a date as e.g. "Jan 2026". */
export function formatMonthYear(d: LocalDate): string {
  return `${MONTH_ABBR[d.monthValue() - 1]} ${d.year()}`;
}
