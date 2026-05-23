import { inject } from '@angular/core';
import { CanActivateFn, Router, Routes } from '@angular/router';
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
    loadComponent: () => import('./no-access/no-access.component').then(m => m.NoAccessComponent),
  },

  // Login (public route)
  {
    path: 'login',
    loadComponent: () => import('./auth/login.component').then(m => m.LoginComponent),
  },
  {
    path: 'forgot-password',
    loadComponent: () => import('./auth/forgot-password.component').then(m => m.ForgotPasswordComponent),
  },
  {
    path: 'reset-password',
    loadComponent: () => import('./auth/reset-password.component').then(m => m.ResetPasswordComponent),
  },

  // Finances section
  {
    path: 'finances',
    canActivate: [authGuard],
    loadComponent: () => import('./finances/finances-layout.component').then(m => m.FinancesLayoutComponent),
    children: [
      { path: '', redirectTo: 'transactions', pathMatch: 'full' },
      {
        path: 'transactions',
        loadComponent: () =>
          import('./finances/transactions/transaction-list.component').then(m => m.TransactionListComponent),
      },
      {
        path: 'calendar',
        loadComponent: () =>
          import('./finances/calendar/transaction-calendar.component').then(m => m.TransactionCalendarComponent),
      },
      {
        path: 'reconcile/:accountId',
        loadComponent: () =>
          import('./finances/reconcile/reconcile.component').then(m => m.ReconcileComponent),
      },
      {
        path: 'setup/account-types',
        loadComponent: () =>
          import('./finances/setup/account-types-list.component').then(m => m.AccountTypesListComponent),
      },
      {
        path: 'setup/journals',
        loadComponent: () =>
          import('./finances/setup/journals-list.component').then(m => m.JournalsListComponent),
      },
      {
        path: 'setup/accounts',
        loadComponent: () =>
          import('./finances/setup/accounts-list.component').then(m => m.AccountsListComponent),
      },
    ],
  },

  // Contacts section
  {
    path: 'contacts',
    canActivate: [authGuard],
    loadComponent: () => import('./contacts/contacts.component').then(m => m.ContactsComponent),
  },

  // Data Bits section
  {
    path: 'databits',
    canActivate: [authGuard],
    loadComponent: () => import('./databits/databits.component').then(m => m.DatabitsComponent),
  },

  // Reports section
  {
    path: 'reports',
    canActivate: [authGuard],
    loadComponent: () => import('./reports/reports.component').then(m => m.ReportsComponent),
  },
  {
    path: 'reports/balance-sheet',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./reports/balance-sheet/balance-sheet.component').then(m => m.BalanceSheetComponent),
  },
  {
    path: 'reports/profit-loss',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./reports/profit-loss/profit-loss.component').then(m => m.ProfitLossComponent),
  },
  {
    path: 'reports/profit-loss-transactions',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./reports/profit-loss-transactions/profit-loss-transactions.component').then(
        m => m.ProfitLossTransactionsComponent,
      ),
  },
  {
    path: 'reports/multi-period-balance-sheet',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./reports/multi-period-balance-sheet/multi-period-balance-sheet.component').then(m => m.MultiPeriodBalanceSheetComponent),
  },
  {
    path: 'reports/account-running-balance',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./reports/account-running-balance/account-running-balance.component').then(m => m.AccountRunningBalanceComponent),
  },
  {
    path: 'reports/:reportType',
    canActivate: [authGuard],
    loadComponent: () => import('./reports/report-viewer.component').then(m => m.ReportViewerComponent),
  },

  // Admin section
  {
    path: 'admin',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./admin/admin-layout.component').then(m => m.AdminLayoutComponent),
    children: [
      { path: '', redirectTo: 'users', pathMatch: 'full' },
      {
        path: 'users',
        loadComponent: () =>
          import('./admin/users/users.component').then(m => m.UsersComponent),
      },
      {
        path: 'roles',
        loadComponent: () =>
          import('./admin/roles/roles.component').then(m => m.RolesComponent),
      },
      {
        path: 'diagnostics',
        loadComponent: () =>
          import('./diagnostics/diagnostics.component').then(m => m.DiagnosticsComponent),
      },
    ],
  },
];
