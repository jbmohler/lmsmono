/** Formats a `YYYY-MM-DD` report input as e.g. "Jan 15, 2026", for display
 * (report headings, page titles) rather than for another date input. */
export function formatReportDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
