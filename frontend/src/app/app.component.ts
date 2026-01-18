import { Component, inject } from '@angular/core';
import { Router, RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class AppComponent {
  private router = inject(Router);

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
