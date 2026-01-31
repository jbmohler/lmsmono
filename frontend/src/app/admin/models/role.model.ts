import { ItemRef } from '@core/api/api.types';

/** Role entity */
export interface Role {
  id: string;
  role_name: string;
  sort: number;
}

/** Capability entity */
export interface Capability {
  id: string;
  cap_name: string;
  description: string;
}

/** Role capability with permitted status */
export interface RoleCapability {
  capability: ItemRef;
  permitted: boolean;
}

/** Request to create a new role */
export interface RoleCreate {
  role_name: string;
  sort?: number;
}

/** Request to update a role */
export interface RoleUpdate {
  role_name?: string;
  sort?: number;
}

/** Request to update a single role capability */
export interface RoleCapabilityUpdate {
  capability_id: string;
  permitted: boolean;
}
