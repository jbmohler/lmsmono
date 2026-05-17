import { Component, inject, signal, afterNextRender, viewChild, ElementRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-forgot-password',
  templateUrl: './forgot-password.component.html',
  styleUrl: './forgot-password.component.scss',
  imports: [FormsModule, RouterLink],
  host: {
    '(keydown.enter)': 'onSubmit()',
  },
})
export class ForgotPasswordComponent {
  private http = inject(HttpClient);

  private usernameInput = viewChild<ElementRef<HTMLInputElement>>('usernameInput');

  username = '';
  loading = signal(false);
  submitted = signal(false);
  error = signal<string | null>(null);

  constructor() {
    afterNextRender(() => {
      this.usernameInput()?.nativeElement.focus();
    });
  }

  onSubmit(): void {
    if (this.loading() || !this.username) return;

    this.error.set(null);
    this.loading.set(true);

    this.http.post('/api/auth/forgot-password', { username: this.username }).subscribe({
      next: () => {
        this.loading.set(false);
        this.submitted.set(true);
      },
      error: () => {
        this.loading.set(false);
        this.error.set('Something went wrong. Please try again.');
      },
    });
  }
}
