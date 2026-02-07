import { Component, inject, signal, OnInit } from '@angular/core';
import { Router, RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from './core/auth/auth.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class AppComponent implements OnInit {
  private router = inject(Router);
  private auth = inject(AuthService);

  initialized = signal(false);
  isLoggedIn = this.auth.isLoggedIn;
  user = this.auth.user;

  ngOnInit(): void {
    this.auth.checkSession().subscribe({
      next: () => this.initialized.set(true),
      error: () => this.initialized.set(true),
    });
  }

  logout(): void {
    this.auth.logout().subscribe(() => {
      this.router.navigate(['/login']);
    });
  }

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
      }
    }
  }
}
