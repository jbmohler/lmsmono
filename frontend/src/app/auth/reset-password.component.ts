import { Component, inject, signal, afterNextRender, viewChild, ElementRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-reset-password',
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.scss',
  imports: [FormsModule, RouterLink],
  host: {
    '(keydown.enter)': 'onSubmit()',
  },
})
export class ResetPasswordComponent {
  private http = inject(HttpClient);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  private passwordInput = viewChild<ElementRef<HTMLInputElement>>('passwordInput');

  token = this.route.snapshot.queryParamMap.get('token') ?? '';
  newPassword = '';
  confirmPassword = '';
  loading = signal(false);
  success = signal(false);
  error = signal<string | null>(null);

  constructor() {
    afterNextRender(() => {
      this.passwordInput()?.nativeElement.focus();
    });
  }

  onSubmit(): void {
    if (this.loading() || !this.newPassword || !this.confirmPassword) return;

    if (this.newPassword !== this.confirmPassword) {
      this.error.set('Passwords do not match');
      return;
    }

    if (this.newPassword.length < 8) {
      this.error.set('Password must be at least 8 characters');
      return;
    }

    this.error.set(null);
    this.loading.set(true);

    this.http
      .post('/api/auth/reset-password', { token: this.token, new_password: this.newPassword })
      .subscribe({
        next: () => {
          this.success.set(true);
          this.loading.set(false);
          setTimeout(() => this.router.navigate(['/login']), 2000);
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err.error?.detail || 'Reset failed. The link may have expired.');
        },
      });
  }
}
