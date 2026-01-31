import {
  Component,
  signal,
  computed,
  viewChild,
  ElementRef,
  afterNextRender,
  inject,
} from '@angular/core';
import { KeyValuePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { RoleService } from './services/role.service';
import { Role, RoleCapability, RoleCapabilityUpdate } from '../models/role.model';

@Component({
  selector: 'app-roles',
  templateUrl: './roles.component.html',
  styleUrl: './roles.component.scss',
  imports: [FormsModule, KeyValuePipe],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class RolesComponent {
  private roleService = inject(RoleService);

  searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');

  searchQuery = signal('');
  selectedRoleId = signal<string | null>(null);
  mobileShowDetail = signal(false);

  // Selected role data
  selectedRole = signal<Role | null>(null);
  roleCapabilities = signal<RoleCapability[]>([]);

  // Edit mode state
  editMode = signal(false);
  editRoleName = signal('');
  editSort = signal<number>(0);

  // Loading and error state
  loading = signal(false);
  saving = signal(false);
  error = signal<string | null>(null);

  constructor() {
    afterNextRender(() => {
      this.searchInput()?.nativeElement.focus();
    });
  }

  // Role list from service
  roles = this.roleService.roles;
  capabilitiesByResource = this.roleService.capabilitiesByResource;

  // Client-side filtering
  filteredRoles = computed(() => {
    const query = this.searchQuery().toLowerCase();
    const list = this.roles();

    if (!query) return list;

    return list.filter(r => r.role_name.toLowerCase().includes(query));
  });

  handleKeydown(event: KeyboardEvent): void {
    // Ctrl+Shift+N - new role
    if (event.ctrlKey && event.shiftKey && event.key === 'N') {
      event.preventDefault();
      this.createNewRole();
      return;
    }

    // Ctrl+S - save (only in edit mode)
    if (event.ctrlKey && event.key === 's') {
      event.preventDefault();
      if (this.editMode()) {
        this.saveRole();
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

    // Arrow navigation
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

    // Enter selects first role if none selected
    if (event.key === 'Enter' && isSearchFocused) {
      event.preventDefault();
      const list = this.filteredRoles();
      if (list.length > 0 && !this.selectedRoleId()) {
        this.selectRoleById(list[0].id);
      }
    }
  }

  navigateList(direction: number): void {
    const list = this.filteredRoles();
    if (list.length === 0) return;

    const currentId = this.selectedRoleId();
    const currentIndex = currentId ? list.findIndex(r => r.id === currentId) : -1;
    let newIndex = currentIndex + direction;

    if (newIndex < 0) newIndex = list.length - 1;
    if (newIndex >= list.length) newIndex = 0;

    this.selectRoleById(list[newIndex].id);
  }

  selectRole(role: Role): void {
    this.selectRoleById(role.id);
  }

  async selectRoleById(id: string): Promise<void> {
    if (this.selectedRoleId() === id) {
      this.mobileShowDetail.set(true);
      return;
    }

    this.selectedRoleId.set(id);
    this.selectedRole.set(null);
    this.roleCapabilities.set([]);
    this.editMode.set(false);
    this.mobileShowDetail.set(true);
    this.loading.set(true);
    this.error.set(null);

    try {
      const [roleResponse, capsResponse] = await Promise.all([
        firstValueFrom(this.roleService.getById(id)),
        firstValueFrom(this.roleService.getRoleCapabilities(id)),
      ]);

      if (this.selectedRoleId() === id) {
        this.selectedRole.set(roleResponse.data);
        this.roleCapabilities.set(capsResponse.data);
        this.resetEditFields(roleResponse.data);
      }
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to load role');
    } finally {
      this.loading.set(false);
    }
  }

  resetEditFields(role: Role): void {
    this.editRoleName.set(role.role_name);
    this.editSort.set(role.sort);
  }

  enterEditMode(): void {
    this.editMode.set(true);
  }

  cancelEdit(): void {
    const role = this.selectedRole();
    if (role) {
      this.resetEditFields(role);
    }
    this.editMode.set(false);
  }

  async createNewRole(): Promise<void> {
    this.saving.set(true);
    this.error.set(null);

    try {
      const response = await firstValueFrom(
        this.roleService.create({ role_name: 'New Role' })
      );
      this.roleService.refreshRoles();
      await this.selectRoleById(response.data.id);
      this.editMode.set(true);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to create role');
    } finally {
      this.saving.set(false);
    }
  }

  async saveRole(): Promise<void> {
    const role = this.selectedRole();
    if (!role) return;

    this.saving.set(true);
    this.error.set(null);

    try {
      await firstValueFrom(
        this.roleService.update(role.id, {
          role_name: this.editRoleName(),
          sort: this.editSort(),
        })
      );
      this.roleService.refreshRoles();

      // Reload role
      const response = await firstValueFrom(this.roleService.getById(role.id));
      this.selectedRole.set(response.data);
      this.resetEditFields(response.data);
      this.editMode.set(false);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to save role');
    } finally {
      this.saving.set(false);
    }
  }

  async deleteRole(): Promise<void> {
    const role = this.selectedRole();
    if (!role) return;

    if (!confirm(`Delete role "${role.role_name}"?`)) {
      return;
    }

    this.saving.set(true);
    this.error.set(null);

    try {
      await firstValueFrom(this.roleService.delete(role.id));
      this.roleService.refreshRoles();
      this.selectedRoleId.set(null);
      this.selectedRole.set(null);
      this.roleCapabilities.set([]);
      this.editMode.set(false);
      this.mobileShowDetail.set(false);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to delete role');
    } finally {
      this.saving.set(false);
    }
  }

  async toggleCapability(capabilityId: string, currentPermitted: boolean): Promise<void> {
    const role = this.selectedRole();
    if (!role || !this.editMode()) return;

    this.saving.set(true);
    this.error.set(null);

    try {
      const updates: RoleCapabilityUpdate[] = [
        { capability_id: capabilityId, permitted: !currentPermitted },
      ];

      const response = await firstValueFrom(
        this.roleService.updateRoleCapabilities(role.id, updates)
      );
      this.roleCapabilities.set(response.data);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to update capability');
    } finally {
      this.saving.set(false);
    }
  }

  // Get capability permitted status
  isCapabilityPermitted(capabilityId: string): boolean {
    const caps = this.roleCapabilities();
    const cap = caps.find(c => c.capability.id === capabilityId);
    return cap?.permitted ?? false;
  }

  // Helper to get resource display name
  getResourceDisplayName(resource: string): string {
    const names: Record<string, string> = {
      accounts: 'Accounts',
      contacts: 'Contacts',
      transactions: 'Transactions',
      journals: 'Journals',
      reports: 'Reports',
      admin: 'Administration',
    };
    return names[resource] ?? resource;
  }

  // Helper to get action display name from cap_name
  getActionDisplayName(capName: string): string {
    const [, action] = capName.split(':');
    const names: Record<string, string> = {
      read: 'View',
      write: 'Edit',
      passwords: 'View Passwords',
      roles: 'Manage Roles',
      users: 'Manage Users',
    };
    return names[action] ?? action;
  }

  trackById(_index: number, role: Role): string {
    return role.id;
  }
}
