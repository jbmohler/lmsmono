import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'finances/transactions', pathMatch: 'full' },

  // Finances section
  {
    path: 'finances',
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
    loadComponent: () => import('./contacts/contacts.component').then(m => m.ContactsComponent),
  },

  // Reports section
  {
    path: 'reports',
    loadComponent: () => import('./reports/reports.component').then(m => m.ReportsComponent),
  },
  {
    path: 'reports/:reportType',
    loadComponent: () => import('./reports/report-viewer.component').then(m => m.ReportViewerComponent),
  },

  // Diagnostics (dev tool)
  {
    path: 'diagnostics',
    loadComponent: () => import('./diagnostics/diagnostics.component').then(m => m.DiagnosticsComponent),
  },

  // Admin section
  {
    path: 'admin',
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
    ],
  },
];
