import { Injectable, inject, computed } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Subject } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';

import { ApiService } from '../../../core/api/api.service';
import { ColumnMeta } from '../../../core/api/api.types';
import {
  Capability,
  Role,
  RoleCapability,
  RoleCapabilityUpdate,
  RoleCreate,
  RoleUpdate,
} from '../../models/role.model';

/**
 * Service for role and capability operations with reactive state.
 */
@Injectable({ providedIn: 'root' })
export class RoleService {
  private api = inject(ApiService);

  // Role list with refresh trigger
  private refreshRoles$ = new Subject<void>();

  private rolesResponse = toSignal(
    this.refreshRoles$.pipe(
      startWith(undefined),
      switchMap(() => this.api.getMany<Role>('/api/roles'))
    )
  );

  /** All roles */
  roles = computed(() => this.rolesResponse()?.data ?? []);

  /** Column metadata for roles */
  columns = computed<ColumnMeta[]>(() => this.rolesResponse()?.columns ?? []);

  // Capabilities (static reference data)
  private capabilitiesResponse = toSignal(
    this.api.getMany<Capability>('/api/capabilities')
  );

  /** All capabilities */
  capabilities = computed(() => this.capabilitiesResponse()?.data ?? []);

  /** Capabilities grouped by resource prefix (e.g., "accounts", "contacts") */
  capabilitiesByResource = computed(() => {
    const caps = this.capabilities();
    const grouped = new Map<string, Capability[]>();

    for (const cap of caps) {
      const [resource] = cap.cap_name.split(':');
      const group = grouped.get(resource) ?? [];
      group.push(cap);
      grouped.set(resource, group);
    }

    return grouped;
  });

  /** Trigger a refresh of the role list */
  refreshRoles(): void {
    this.refreshRoles$.next();
  }

  /** Get a single role by ID */
  getById(id: string) {
    return this.api.getOne<Role>(`/api/roles/${id}`);
  }

  /** Create a new role */
  create(data: RoleCreate) {
    return this.api.create<Role, RoleCreate>('/api/roles', data);
  }

  /** Update an existing role */
  update(id: string, data: RoleUpdate) {
    return this.api.update<Role, RoleUpdate>(`/api/roles/${id}`, data);
  }

  /** Delete a role */
  delete(id: string) {
    return this.api.delete(`/api/roles/${id}`);
  }

  /** Get capabilities for a role with permitted status */
  getRoleCapabilities(roleId: string) {
    return this.api.getMany<RoleCapability>(`/api/roles/${roleId}/capabilities`);
  }

  /** Bulk update role capabilities */
  updateRoleCapabilities(roleId: string, updates: RoleCapabilityUpdate[]) {
    return this.api.update<RoleCapability[], RoleCapabilityUpdate[]>(
      `/api/roles/${roleId}/capabilities`,
      updates
    );
  }
}
