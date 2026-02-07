import { Component, inject, signal, afterNextRender, viewChild, ElementRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../core/auth/auth.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
  imports: [FormsModule],
  host: {
    '(keydown.enter)': 'onSubmit()',
  },
})
export class LoginComponent {
  private auth = inject(AuthService);
  private router = inject(Router);

  private usernameInput = viewChild<ElementRef<HTMLInputElement>>('usernameInput');

  username = '';
  password = '';
  error = signal<string | null>(null);
  loading = signal(false);

  constructor() {
    afterNextRender(() => {
      this.usernameInput()?.nativeElement.focus();
    });
  }

  onSubmit(): void {
    if (this.loading() || !this.username || !this.password) {
      return;
    }

    this.error.set(null);
    this.loading.set(true);

    this.auth.login(this.username, this.password).subscribe({
      next: () => {
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(err.error?.detail || 'Login failed');
      },
    });
  }
}
