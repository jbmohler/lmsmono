import { Component, signal } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-finances-layout',
  templateUrl: './finances-layout.component.html',
  styleUrl: './finances-layout.component.scss',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
})
export class FinancesLayoutComponent {
  setupExpanded = signal(false);

  toggleSetup(): void {
    this.setupExpanded.update(v => !v);
  }
}
