import {
  Component,
  signal,
  computed,
  viewChild,
  ElementRef,
  afterNextRender,
  inject,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { UserService } from './services/user.service';
import { User, UserRole, UserRoleUpdate } from '../models/user.model';

@Component({
  selector: 'app-users',
  templateUrl: './users.component.html',
  styleUrl: './users.component.scss',
  imports: [FormsModule],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class UsersComponent {
  private userService = inject(UserService);

  searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');

  searchQuery = signal('');
  selectedUserId = signal<string | null>(null);
  mobileShowDetail = signal(false);

  // Selected user data
  selectedUser = signal<User | null>(null);
  userRoles = signal<UserRole[]>([]);

  // Edit mode state
  editMode = signal(false);
  editUsername = signal('');
  editFullName = signal('');
  editDescr = signal('');
  editInactive = signal(false);

  // Loading and error state
  loading = signal(false);
  saving = signal(false);
  error = signal<string | null>(null);

  constructor() {
    afterNextRender(() => {
      this.searchInput()?.nativeElement.focus();
    });
  }

  // User list from service
  users = this.userService.users;

  // Client-side filtering
  filteredUsers = computed(() => {
    const query = this.searchQuery().toLowerCase();
    const list = this.users();

    if (!query) return list;

    return list.filter(
      u =>
        u.username.toLowerCase().includes(query) ||
        (u.full_name && u.full_name.toLowerCase().includes(query))
    );
  });

  handleKeydown(event: KeyboardEvent): void {
    // Ctrl+Shift+N - new user
    if (event.ctrlKey && event.shiftKey && event.key === 'N') {
      event.preventDefault();
      this.createNewUser();
      return;
    }

    // Ctrl+S - save (only in edit mode)
    if (event.ctrlKey && event.key === 's') {
      event.preventDefault();
      if (this.editMode()) {
        this.saveUser();
      }
      return;
    }

    // Escape - cancel edit or close mobile detail
    if (event.key === 'Escape') {
      if (this.editMode()) {
        this.cancelEdit();
      } else if (this.mobileShowDetail()) {
        this.mobileShowDetail.set(false);
      }
      return;
    }

    const target = event.target as HTMLElement;
    const isSearchFocused = target === this.searchInput()?.nativeElement;

    // Arrow navigation (only when not in other inputs)
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      const isOtherInputFocused =
        !isSearchFocused &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT');

      if (!isOtherInputFocused) {
        event.preventDefault();
        this.navigateList(event.key === 'ArrowDown' ? 1 : -1);
      }
    }

    // Enter selects first user if none selected
    if (event.key === 'Enter' && isSearchFocused) {
      event.preventDefault();
      const list = this.filteredUsers();
      if (list.length > 0 && !this.selectedUserId()) {
        this.selectUserById(list[0].id);
      }
    }
  }

  navigateList(direction: number): void {
    const list = this.filteredUsers();
    if (list.length === 0) return;

    const currentId = this.selectedUserId();
    const currentIndex = currentId ? list.findIndex(u => u.id === currentId) : -1;
    let newIndex = currentIndex + direction;

    if (newIndex < 0) newIndex = list.length - 1;
    if (newIndex >= list.length) newIndex = 0;

    this.selectUserById(list[newIndex].id);
  }

  selectUser(user: User): void {
    this.selectUserById(user.id);
  }

  async selectUserById(id: string): Promise<void> {
    if (this.selectedUserId() === id) {
      this.mobileShowDetail.set(true);
      return;
    }

    this.selectedUserId.set(id);
    this.selectedUser.set(null);
    this.userRoles.set([]);
    this.editMode.set(false);
    this.mobileShowDetail.set(true);
    this.loading.set(true);
    this.error.set(null);

    try {
      const [userResponse, rolesResponse] = await Promise.all([
        firstValueFrom(this.userService.getById(id)),
        firstValueFrom(this.userService.getUserRoles(id)),
      ]);

      if (this.selectedUserId() === id) {
        this.selectedUser.set(userResponse.data);
        this.userRoles.set(rolesResponse.data);
        this.resetEditFields(userResponse.data);
      }
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to load user');
    } finally {
      this.loading.set(false);
    }
  }

  resetEditFields(user: User): void {
    this.editUsername.set(user.username);
    this.editFullName.set(user.full_name ?? '');
    this.editDescr.set(user.descr ?? '');
    this.editInactive.set(user.inactive);
  }

  enterEditMode(): void {
    this.editMode.set(true);
  }

  cancelEdit(): void {
    const user = this.selectedUser();
    if (user) {
      this.resetEditFields(user);
    }
    this.editMode.set(false);
  }

  async createNewUser(): Promise<void> {
    this.saving.set(true);
    this.error.set(null);

    try {
      const response = await firstValueFrom(
        this.userService.create({ username: 'newuser' })
      );
      this.userService.refreshUsers();
      await this.selectUserById(response.data.id);
      this.editMode.set(true);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      this.saving.set(false);
    }
  }

  async saveUser(): Promise<void> {
    const user = this.selectedUser();
    if (!user) return;

    this.saving.set(true);
    this.error.set(null);

    try {
      await firstValueFrom(
        this.userService.update(user.id, {
          username: this.editUsername(),
          full_name: this.editFullName() || null,
          descr: this.editDescr() || null,
          inactive: this.editInactive(),
        })
      );
      this.userService.refreshUsers();

      // Reload user
      const response = await firstValueFrom(this.userService.getById(user.id));
      this.selectedUser.set(response.data);
      this.resetEditFields(response.data);
      this.editMode.set(false);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to save user');
    } finally {
      this.saving.set(false);
    }
  }

  async deleteUser(): Promise<void> {
    const user = this.selectedUser();
    if (!user) return;

    if (!confirm(`Deactivate user "${user.username}"? This will set the user to inactive.`)) {
      return;
    }

    this.saving.set(true);
    this.error.set(null);

    try {
      await firstValueFrom(this.userService.delete(user.id));
      this.userService.refreshUsers();
      this.selectedUserId.set(null);
      this.selectedUser.set(null);
      this.userRoles.set([]);
      this.editMode.set(false);
      this.mobileShowDetail.set(false);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to deactivate user');
    } finally {
      this.saving.set(false);
    }
  }

  async toggleRole(roleId: string, currentAssigned: boolean): Promise<void> {
    const user = this.selectedUser();
    if (!user || !this.editMode()) return;

    this.saving.set(true);
    this.error.set(null);

    try {
      const updates: UserRoleUpdate[] = [
        { role_id: roleId, assigned: !currentAssigned },
      ];

      const response = await firstValueFrom(
        this.userService.updateUserRoles(user.id, updates)
      );
      this.userRoles.set(response.data);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to update role');
    } finally {
      this.saving.set(false);
    }
  }

  // Get role assigned status
  isRoleAssigned(roleId: string): boolean {
    const roles = this.userRoles();
    const role = roles.find(r => r.role.id === roleId);
    return role?.assigned ?? false;
  }

  trackById(_index: number, user: User): string {
    return user.id;
  }

  trackByRoleId(_index: number, role: UserRole): string {
    return role.role.id;
  }
}
