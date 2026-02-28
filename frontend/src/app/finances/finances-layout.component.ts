import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterOutlet, RouterLink, RouterLinkActive, NavigationEnd } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map, startWith } from 'rxjs/operators';

import { AccountService } from '@finances/services/account.service';

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

  /** Balance-sheet accounts excluding retained-earnings types — shown in the Reconcile dropdown. */
  reconcilableAccounts = computed(() => {
    const accounts = this.accountService.accounts();
    const types = this.accountService.accountTypes();
    const eligibleTypeIds = new Set(
      types.filter(t => t.balance_sheet && !t.retained_earnings).map(t => t.id)
    );
    return accounts.filter(a => eligibleTypeIds.has(a.account_type.id));
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
