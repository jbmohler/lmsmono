import { Component, ChangeDetectionStrategy } from '@angular/core';
import { RouterLink } from '@angular/router';

/** Reports sharing a group share its icon. */
type ReportGroup = 'balance-sheet' | 'profit-loss' | 'transaction-detail' | 'other-report';

interface ReportItem {
  id: string;
  name: string;
  description: string;
  group: ReportGroup;
  desktopOnly?: boolean;
}

const GROUP_LABELS: Record<ReportGroup, string> = {
  'balance-sheet': 'Balance sheet',
  'profit-loss': 'Profit & loss',
  'transaction-detail': 'Transaction detail',
  'other-report': 'Other',
};

@Component({
  selector: 'app-reports',
  templateUrl: './reports.component.html',
  styleUrl: './reports.component.scss',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [RouterLink],
})
export class ReportsComponent {
  // Ordered by subject: account balances, then profit & loss, then
  // transaction detail, then everything else.
  reports: ReportItem[] = [
    {
      id: 'balance-sheet',
      name: 'Balance Sheet',
      description: 'Assets, liabilities, and equity at a point in time',
      group: 'balance-sheet',
    },
    {
      id: 'multi-period-balance-sheet',
      name: 'Multi-Period Balance Sheet',
      description: 'Balance sheet compared across annual periods',
      desktopOnly: true,
      group: 'balance-sheet',
    },
    {
      id: 'account-running-balance',
      name: 'Account Running Balance',
      description: 'Ledger view of a single account with speculative future transactions',
      group: 'transaction-detail',
    },
    {
      id: 'profit-loss',
      name: 'Profit & Loss',
      description: 'Income and expenses over a period',
      group: 'profit-loss',
    },
    {
      id: 'multi-period-profit-loss',
      name: 'Multi-Period Profit & Loss',
      description: 'Income and expenses compared across rolling periods',
      desktopOnly: true,
      group: 'profit-loss',
    },
    {
      id: 'profit-loss-transactions',
      name: 'P&L Transactions',
      description: 'Individual transactions behind the P&L',
      group: 'transaction-detail',
    },
    {
      id: 'payee-summary',
      name: 'Payee Summary',
      description: 'Spending totals grouped by payee for a single account',
      group: 'transaction-detail',
    },
    {
      id: 'account-activity',
      name: 'Account Activity',
      description: 'Detailed activity by account',
      group: 'transaction-detail',
    },
    {
      id: 'tax-summary',
      name: 'Tax Summary',
      description: 'Tax-relevant totals and categories',
      group: 'other-report',
    },
  ];

  groupLabel(group: ReportGroup): string {
    return GROUP_LABELS[group];
  }
}
