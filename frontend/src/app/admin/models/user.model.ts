import { ItemRef } from '@core/api/api.types';

/** User entity */
export interface User {
  id: string;
  username: string;
  full_name: string | null;
  descr: string | null;
  inactive: boolean;
}

/** User role with assigned status */
export interface UserRole {
  role: ItemRef;
  assigned: boolean;
}

/** Request to create a new user */
export interface UserCreate {
  username: string;
  full_name?: string | null;
  descr?: string | null;
}

/** Request to update a user */
export interface UserUpdate {
  username?: string;
  full_name?: string | null;
  descr?: string | null;
  inactive?: boolean;
}

/** Request to update a single user role */
export interface UserRoleUpdate {
  role_id: string;
  assigned: boolean;
}
