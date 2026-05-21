import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterOutlet, RouterLink, RouterLinkActive, NavigationEnd } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map, startWith } from 'rxjs/operators';

import { AccountService } from '@finances/services/account.service';
import { Account } from '@finances/models/account.model';

@Component({
  selector: 'app-finances-layout',
  templateUrl: './finances-layout.component.html',
  styleUrl: './finances-layout.component.scss',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
})
export class FinancesLayoutComponent {
  private accountService = inject(AccountService);
  private router = inject(Router);

  setupExpanded = signal(false);

  private oneYearAgo = (() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 1);
    return d.toISOString().slice(0, 10);
  })();

  /** Reconcilable accounts (balance sheet, non-retained-earnings, active last year) grouped by type. */
  reconcilableAccountsByType = computed(() => {
    const accounts = this.accountService.accounts();
    const types = this.accountService.accountTypes();
    const eligibleTypeIds = new Set(
      types.filter(t => t.balance_sheet && !t.retained_earnings).map(t => t.id)
    );
    const grouped = new Map<string, Account[]>();
    for (const account of accounts) {
      if (!eligibleTypeIds.has(account.account_type.id)) continue;
      if (!account.last_activity || account.last_activity < this.oneYearAgo) continue;
      const typeName = account.account_type.name;
      const group = grouped.get(typeName) ?? [];
      group.push(account);
      grouped.set(typeName, group);
    }
    return [...grouped.entries()];
  });

  /** Account ID currently shown in the reconcile route, for dropdown sync. */
  selectedReconcileId = toSignal(
    this.router.events.pipe(
      filter(e => e instanceof NavigationEnd),
      startWith(null),
      map(() => {
        const match = this.router.url.match(/\/reconcile\/([^/?#]+)/);
        return match ? match[1] : '';
      }),
    ),
    { initialValue: '' },
  );

  navigateToReconcile(event: Event): void {
    const id = (event.target as HTMLSelectElement).value;
    if (id) {
      this.router.navigate(['/finances/reconcile', id]);
    }
  }

  toggleSetup(): void {
    this.setupExpanded.update(v => !v);
  }
}
