export interface NavTab {
  path: string;
  label: string;
  hasAccess: (caps: Set<string>) => boolean;
}

export const NAV_TABS: NavTab[] = [
  { path: '/contacts', label: 'Contacts', hasAccess: caps => caps.has('contacts:read') },
  { path: '/databits', label: 'Data Bits', hasAccess: caps => caps.has('databits:read') },
  { path: '/finances', label: 'Finances', hasAccess: caps => caps.has('transactions:read') },
  { path: '/reports', label: 'Reports', hasAccess: caps => caps.has('reports:read') },
  { path: '/admin', label: 'Admin', hasAccess: caps => caps.has('admin:users') || caps.has('admin:roles') },
];
