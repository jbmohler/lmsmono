import { Component, inject, computed } from '@angular/core';
import { Router, RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from './core/auth/auth.service';
import { UserMenuComponent } from '@shared/components/user-menu/user-menu.component';
import { NAV_TABS } from './nav-tabs';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, UserMenuComponent],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class AppComponent {
  private router = inject(Router);
  private auth = inject(AuthService);

  isLoggedIn = this.auth.isLoggedIn;

  visibleTabs = computed(() => {
    const caps = this.auth.capabilities();
    return NAV_TABS.filter(t => t.hasAccess(caps));
  });

  handleKeydown(event: KeyboardEvent): void {
    if (event.ctrlKey && event.shiftKey) {
      switch (event.key.toUpperCase()) {
        case 'R':
          event.preventDefault();
          this.router.navigate(['/finances/transactions']);
          break;
        case 'K':
          event.preventDefault();
          this.router.navigate(['/contacts']);
          break;
        case 'D':
          event.preventDefault();
          this.router.navigate(['/databits']);
          break;
      }
    }
  }
}
