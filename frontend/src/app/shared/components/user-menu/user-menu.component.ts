import {
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
  viewChildren,
  afterNextRender,
} from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '@core/auth/auth.service';

/**
 * Avatar button in the header that opens a keyboard-accessible menu with the
 * sign-out actions. Closes on Escape or an outside click, and returns focus to
 * the avatar trigger when dismissed with the keyboard.
 */
@Component({
  selector: 'app-user-menu',
  templateUrl: './user-menu.component.html',
  styleUrl: './user-menu.component.scss',
  host: {
    '(document:click)': 'onDocumentClick($event)',
  },
})
export class UserMenuComponent {
  private auth = inject(AuthService);
  private router = inject(Router);
  private host = inject(ElementRef<HTMLElement>);

  private trigger = viewChild<ElementRef<HTMLButtonElement>>('trigger');
  private menuItems = viewChildren<ElementRef<HTMLButtonElement>>('menuItem');

  open = signal(false);
  user = this.auth.user;

  initials = computed(() => {
    const u = this.user();
    if (!u) return '?';
    const source = u.fullName?.trim() || u.username;
    const parts = source.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return source.slice(0, 2).toUpperCase();
  });

  toggle(): void {
    if (this.open()) {
      this.close();
    } else {
      this.openMenu();
    }
  }

  private openMenu(): void {
    this.open.set(true);
    afterNextRender(() => this.focusItem(0));
  }

  private close(focusTrigger = false): void {
    this.open.set(false);
    if (focusTrigger) {
      this.trigger()?.nativeElement.focus();
    }
  }

  onDocumentClick(event: MouseEvent): void {
    if (this.open() && !this.host.nativeElement.contains(event.target as Node)) {
      this.close();
    }
  }

  /** Arrow/Home/End/Escape navigation while the menu is open. */
  onMenuKeydown(event: KeyboardEvent): void {
    const items = this.menuItems();
    const current = items.findIndex(i => i.nativeElement === document.activeElement);

    switch (event.key) {
      case 'Escape':
        event.preventDefault();
        this.close(true);
        break;
      case 'ArrowDown':
        event.preventDefault();
        this.focusItem((current + 1) % items.length);
        break;
      case 'ArrowUp':
        event.preventDefault();
        this.focusItem((current - 1 + items.length) % items.length);
        break;
      case 'Home':
        event.preventDefault();
        this.focusItem(0);
        break;
      case 'End':
        event.preventDefault();
        this.focusItem(items.length - 1);
        break;
    }
  }

  /** ArrowDown on the trigger opens the menu and moves into it. */
  onTriggerKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown' && !this.open()) {
      event.preventDefault();
      this.openMenu();
    }
  }

  private focusItem(index: number): void {
    this.menuItems()[index]?.nativeElement.focus();
  }

  signOut(): void {
    this.close();
    this.auth.logout().subscribe(() => this.router.navigate(['/login']));
  }

  signOutAll(): void {
    if (
      !confirm(
        'Sign out of every device, including any "remember me" sessions? You will need to sign in again everywhere.'
      )
    ) {
      return;
    }
    this.close();
    this.auth.logoutAll().subscribe(() => this.router.navigate(['/login']));
  }
}
