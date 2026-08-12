import { inject } from '@angular/core';
import { CanActivateFn, ResolveFn, Router, Routes } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from './core/auth/auth.service';
import { authGuard } from './core/auth/auth.guard';
import { NAV_TABS } from './nav-tabs';

const homeGuard: CanActivateFn = () => {
  const router = inject(Router);
  const auth = inject(AuthService);

  const redirect = () => {
    if (!auth.isLoggedIn()) return router.createUrlTree(['/login']);
    const first = NAV_TABS.find(t => t.hasAccess(auth.capabilities()));
    return router.createUrlTree([first?.path ?? '/no-access']);
  };

  if (auth.initialized()) return redirect();

  return auth.checkSession().pipe(map(redirect));
};

/** Title for the catch-all `reports/:reportType` route — humanizes the id for
 * report types that don't have their own dedicated route/component yet. */
const resolveReportTitle: ResolveFn<string> = route => {
  const reportType = route.paramMap.get('reportType') ?? '';
  return reportType
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    canActivate: [homeGuard],
    children: [],
  },

  // No roles assigned — shown inside the shell so the user can sign out
  {
    path: 'no-access',
    canActivate: [authGuard],
    title: 'No Access',
    loadComponent: () => import('./no-access/no-access.component').then(m => m.NoAccessComponent),
  },

  // Login (public route)
  {
    path: 'login',
    title: 'Login',
    loadComponent: () => import('./auth/login.component').then(m => m.LoginComponent),
  },
  {
    path: 'forgot-password',
    title: 'Forgot Password',
    loadComponent: () => import('./auth/forgot-password.component').then(m => m.ForgotPasswordComponent),
  },
  {
    path: 'reset-password',
    title: 'Reset Password',
    loadComponent: () => import('./auth/reset-password.component').then(m => m.ResetPasswordComponent),
  },

  // Finances section
  {
    path: 'finances',
    canActivate: [authGuard],
    title: 'Finances',
    loadComponent: () => import('./finances/finances-layout.component').then(m => m.FinancesLayoutComponent),
    children: [
      { path: '', redirectTo: 'transactions', pathMatch: 'full' },
      {
        path: 'transactions',
        title: 'Transactions',
        loadComponent: () =>
          import('./finances/transactions/transaction-list.component').then(m => m.TransactionListComponent),
      },
      {
        path: 'calendar',
        title: 'Calendar',
        loadComponent: () =>
          import('./finances/calendar/transaction-calendar.component').then(m => m.TransactionCalendarComponent),
      },
      {
        path: 'reconcile/:accountId',
        title: 'Reconcile',
        loadComponent: () =>
          import('./finances/reconcile/reconcile.component').then(m => m.ReconcileComponent),
      },
      {
        path: 'setup/account-types',
        title: 'Account Types',
        loadComponent: () =>
          import('./finances/setup/account-types-list.component').then(m => m.AccountTypesListComponent),
      },
      {
        path: 'setup/journals',
        title: 'Journals',
        loadComponent: () =>
          import('./finances/setup/journals-list.component').then(m => m.JournalsListComponent),
      },
      {
        path: 'setup/accounts',
        title: 'Accounts',
        loadComponent: () =>
          import('./finances/setup/accounts-list.component').then(m => m.AccountsListComponent),
      },
    ],
  },

  // Contacts section
  {
    path: 'contacts',
    canActivate: [authGuard],
    title: 'Contacts',
    loadComponent: () => import('./contacts/contacts.component').then(m => m.ContactsComponent),
  },

  // Data Bits section
  {
    path: 'databits',
    canActivate: [authGuard],
    title: 'Data Bits',
    loadComponent: () => import('./databits/databits.component').then(m => m.DatabitsComponent),
  },

  // Reports section
  {
    path: 'reports',
    canActivate: [authGuard],
    title: 'Reports',
    loadComponent: () => import('./reports/reports.component').then(m => m.ReportsComponent),
  },
  {
    path: 'reports/balance-sheet',
    canActivate: [authGuard],
    title: 'Balance Sheet',
    loadComponent: () =>
      import('./reports/balance-sheet/balance-sheet.component').then(m => m.BalanceSheetComponent),
  },
  {
    path: 'reports/profit-loss',
    canActivate: [authGuard],
    title: 'Profit & Loss',
    loadComponent: () =>
      import('./reports/profit-loss/profit-loss.component').then(m => m.ProfitLossComponent),
  },
  {
    path: 'reports/profit-loss-transactions',
    canActivate: [authGuard],
    title: 'P&L Transactions',
    loadComponent: () =>
      import('./reports/profit-loss-transactions/profit-loss-transactions.component').then(
        m => m.ProfitLossTransactionsComponent,
      ),
  },
  {
    path: 'reports/multi-period-profit-loss',
    canActivate: [authGuard],
    title: 'Multi-Period Profit & Loss',
    loadComponent: () =>
      import('./reports/multi-period-profit-loss/multi-period-profit-loss.component').then(m => m.MultiPeriodProfitLossComponent),
  },
  {
    path: 'reports/multi-period-balance-sheet',
    canActivate: [authGuard],
    title: 'Multi-Period Balance Sheet',
    loadComponent: () =>
      import('./reports/multi-period-balance-sheet/multi-period-balance-sheet.component').then(m => m.MultiPeriodBalanceSheetComponent),
  },
  {
    path: 'reports/account-running-balance',
    canActivate: [authGuard],
    title: 'Account Running Balance',
    loadComponent: () =>
      import('./reports/account-running-balance/account-running-balance.component').then(m => m.AccountRunningBalanceComponent),
  },
  {
    path: 'reports/payee-summary',
    canActivate: [authGuard],
    title: 'Payee Summary',
    loadComponent: () =>
      import('./reports/payee-summary/payee-summary.component').then(m => m.PayeeSummaryComponent),
  },
  {
    path: 'reports/:reportType',
    canActivate: [authGuard],
    title: resolveReportTitle,
    loadComponent: () => import('./reports/report-viewer.component').then(m => m.ReportViewerComponent),
  },

  // Admin section
  {
    path: 'admin',
    canActivate: [authGuard],
    title: 'Admin',
    loadComponent: () =>
      import('./admin/admin-layout.component').then(m => m.AdminLayoutComponent),
    children: [
      { path: '', redirectTo: 'users', pathMatch: 'full' },
      {
        path: 'users',
        title: 'Users',
        loadComponent: () =>
          import('./admin/users/users.component').then(m => m.UsersComponent),
      },
      {
        path: 'roles',
        title: 'Roles',
        loadComponent: () =>
          import('./admin/roles/roles.component').then(m => m.RolesComponent),
      },
      {
        path: 'diagnostics',
        title: 'Diagnostics',
        loadComponent: () =>
          import('./diagnostics/diagnostics.component').then(m => m.DiagnosticsComponent),
      },
    ],
  },
];
