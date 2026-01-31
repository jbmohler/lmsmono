import { Injectable, inject, computed } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Subject } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';

import { ApiService } from '@core/api/api.service';
import { ColumnMeta } from '@core/api/api.types';
import {
  User,
  UserCreate,
  UserRole,
  UserRoleUpdate,
  UserUpdate,
} from '@admin/models/user.model';

/**
 * Service for user operations with reactive state.
 */
@Injectable({ providedIn: 'root' })
export class UserService {
  private api = inject(ApiService);

  // User list with refresh trigger
  private refreshUsers$ = new Subject<void>();

  private usersResponse = toSignal(
    this.refreshUsers$.pipe(
      startWith(undefined),
      switchMap(() => this.api.getMany<User>('/api/users'))
    )
  );

  /** All users */
  users = computed(() => this.usersResponse()?.data ?? []);

  /** Column metadata for users */
  columns = computed<ColumnMeta[]>(() => this.usersResponse()?.columns ?? []);

  /** Trigger a refresh of the user list */
  refreshUsers(): void {
    this.refreshUsers$.next();
  }

  /** Get a single user by ID */
  getById(id: string) {
    return this.api.getOne<User>(`/api/users/${id}`);
  }

  /** Create a new user */
  create(data: UserCreate) {
    return this.api.create<User, UserCreate>('/api/users', data);
  }

  /** Update an existing user */
  update(id: string, data: UserUpdate) {
    return this.api.update<User, UserUpdate>(`/api/users/${id}`, data);
  }

  /** Delete (soft-delete) a user */
  delete(id: string) {
    return this.api.delete(`/api/users/${id}`);
  }

  /** Get roles for a user with assigned status */
  getUserRoles(userId: string) {
    return this.api.getMany<UserRole>(`/api/users/${userId}/roles`);
  }

  /** Bulk update user roles */
  updateUserRoles(userId: string, updates: UserRoleUpdate[]) {
    return this.api.update<UserRole[], UserRoleUpdate[]>(
      `/api/users/${userId}/roles`,
      updates
    );
  }
}
