import { Injectable, inject, computed, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Subject, of } from 'rxjs';
import { startWith, switchMap, catchError, tap } from 'rxjs/operators';

import { ApiService } from '../../core/api/api.service';
import {
  Persona,
  ContactBit,
  ContactEmail,
  ContactPhone,
  ContactAddress,
  ContactUrl,
} from '../contacts.model';

/**
 * API response types (snake_case from backend)
 */
interface ApiPersona {
  id: string;
  is_corporate: boolean;
  last_name: string;
  first_name: string | null;
  title: string | null;
  organization: string | null;
  memo: string | null;
  birthday: string | null;
  anniversary: string | null;
  entity_name: string;
  bits?: ApiBit[];
}

interface ApiPersonaListItem {
  id: string;
  entity_name: string;
  is_corporate: boolean;
  organization: string | null;
  primary_email: string | null;
  primary_phone: string | null;
}

interface ApiBit {
  id: string;
  bit_type: string;
  name: string | null;
  memo: string | null;
  is_primary: boolean;
  bit_sequence: number;
  // Type-specific fields (flattened from bit_data)
  email?: string;
  number?: string;
  address1?: string;
  address2?: string;
  city?: string;
  state?: string;
  zip?: string;
  country?: string;
  url?: string;
  username?: string;
  // URL password fields
  has_password?: boolean;
  pw_reset_dt?: string | null;
  pw_next_reset_dt?: string | null;
}

/**
 * Request types for creating/updating
 */
export interface PersonaCreate {
  is_corporate: boolean;
  last_name: string;
  first_name?: string | null;
  title?: string | null;
  organization?: string | null;
  memo?: string | null;
  birthday?: string | null;
  anniversary?: string | null;
}

export interface PersonaUpdate {
  is_corporate?: boolean;
  last_name?: string;
  first_name?: string | null;
  title?: string | null;
  organization?: string | null;
  memo?: string | null;
  birthday?: string | null;
  anniversary?: string | null;
}

export interface BitCreate {
  bit_type: string;
  name?: string | null;
  memo?: string | null;
  is_primary?: boolean;
  bit_sequence?: number;
  email?: string;
  number?: string;
  address1?: string;
  address2?: string;
  city?: string;
  state?: string;
  zip?: string;
  country?: string;
  url?: string;
  username?: string;
  password?: string;
  pw_reset_dt?: string | null;
  pw_next_reset_dt?: string | null;
}

export interface BitUpdate {
  name?: string | null;
  memo?: string | null;
  is_primary?: boolean;
  bit_sequence?: number;
  email?: string;
  number?: string;
  address1?: string;
  address2?: string;
  city?: string;
  state?: string;
  zip?: string;
  country?: string;
  url?: string;
  username?: string;
  password?: string;
  clear_password?: boolean;
  pw_reset_dt?: string | null;
  pw_next_reset_dt?: string | null;
}

export interface BitReorderRequest {
  items: { id: string; bit_sequence: number }[];
}

/**
 * Transform API bit to frontend ContactBit
 */
function transformBit(api: ApiBit): ContactBit {
  const base = {
    id: api.id,
    label: api.name ?? '',
    memo: api.memo ?? '',
    isPrimary: api.is_primary,
    bitSequence: api.bit_sequence,
  };

  switch (api.bit_type) {
    case 'email':
    case 'email_addresses':
      return { ...base, bitType: 'email', email: api.email ?? '' } as ContactEmail;
    case 'phone':
    case 'phone_numbers':
      return { ...base, bitType: 'phone', number: api.number ?? '' } as ContactPhone;
    case 'address':
    case 'street_addresses':
      return {
        ...base,
        bitType: 'address',
        address1: api.address1 ?? '',
        address2: api.address2 ?? '',
        city: api.city ?? '',
        state: api.state ?? '',
        zip: api.zip ?? '',
        country: api.country ?? '',
      } as ContactAddress;
    case 'url':
    case 'urls':
      return {
        ...base,
        bitType: 'url',
        url: api.url ?? '',
        username: api.username ?? '',
        hasPassword: api.has_password ?? false,
        pwResetDt: api.pw_reset_dt ?? null,
        pwNextResetDt: api.pw_next_reset_dt ?? null,
      } as ContactUrl;
    default:
      // Fallback - treat as email
      return { ...base, bitType: 'email', email: '' } as ContactEmail;
  }
}

/**
 * Transform API persona to frontend Persona
 */
function transformPersona(api: ApiPersona): Persona {
  return {
    id: api.id,
    isCorporate: api.is_corporate,
    lastName: api.last_name ?? '',
    firstName: api.first_name ?? '',
    title: api.title ?? '',
    organization: api.organization ?? '',
    memo: api.memo ?? '',
    birthday: api.birthday,
    anniversary: api.anniversary,
    bits: (api.bits ?? []).map(transformBit),
  };
}

/**
 * Transform frontend Persona to API create request
 */
function toPersonaCreate(persona: Persona): PersonaCreate {
  return {
    is_corporate: persona.isCorporate,
    last_name: persona.lastName,
    first_name: persona.firstName || null,
    title: persona.title || null,
    organization: persona.organization || null,
    memo: persona.memo || null,
    birthday: persona.birthday,
    anniversary: persona.anniversary,
  };
}

/**
 * Transform frontend Persona changes to API update request
 */
function toPersonaUpdate(persona: Partial<Persona>): PersonaUpdate {
  const update: PersonaUpdate = {};
  if (persona.isCorporate !== undefined) update.is_corporate = persona.isCorporate;
  if (persona.lastName !== undefined) update.last_name = persona.lastName;
  if (persona.firstName !== undefined) update.first_name = persona.firstName || null;
  if (persona.title !== undefined) update.title = persona.title || null;
  if (persona.organization !== undefined) update.organization = persona.organization || null;
  if (persona.memo !== undefined) update.memo = persona.memo || null;
  if (persona.birthday !== undefined) update.birthday = persona.birthday;
  if (persona.anniversary !== undefined) update.anniversary = persona.anniversary;
  return update;
}

/**
 * Transform frontend ContactBit to API bit create request
 */
function toBitCreate(bit: ContactBit): BitCreate {
  const create: BitCreate = {
    bit_type: bit.bitType,
    name: bit.label || null,
    memo: bit.memo || null,
    is_primary: bit.isPrimary,
    bit_sequence: bit.bitSequence,
  };

  switch (bit.bitType) {
    case 'email':
      create.email = (bit as ContactEmail).email;
      break;
    case 'phone':
      create.number = (bit as ContactPhone).number;
      break;
    case 'address': {
      const addr = bit as ContactAddress;
      create.address1 = addr.address1;
      create.address2 = addr.address2;
      create.city = addr.city;
      create.state = addr.state;
      create.zip = addr.zip;
      create.country = addr.country;
      break;
    }
    case 'url': {
      const urlBit = bit as ContactUrl;
      create.url = urlBit.url;
      create.username = urlBit.username;
      break;
    }
  }

  return create;
}

/**
 * Transform frontend ContactBit to API bit update request
 */
function toBitUpdate(bit: Partial<ContactBit> & { bitType?: string }): BitUpdate {
  const update: BitUpdate = {};

  if ('label' in bit) update.name = bit.label || null;
  if ('memo' in bit) update.memo = bit.memo || null;
  if ('isPrimary' in bit) update.is_primary = bit.isPrimary;
  if ('bitSequence' in bit) update.bit_sequence = bit.bitSequence;

  // Type-specific fields
  if ('email' in bit) update.email = (bit as ContactEmail).email;
  if ('number' in bit) update.number = (bit as ContactPhone).number;
  if ('address1' in bit) update.address1 = (bit as ContactAddress).address1;
  if ('address2' in bit) update.address2 = (bit as ContactAddress).address2;
  if ('city' in bit) update.city = (bit as ContactAddress).city;
  if ('state' in bit) update.state = (bit as ContactAddress).state;
  if ('zip' in bit) update.zip = (bit as ContactAddress).zip;
  if ('country' in bit) update.country = (bit as ContactAddress).country;
  if ('url' in bit) update.url = (bit as ContactUrl).url;
  if ('username' in bit) update.username = (bit as ContactUrl).username;

  return update;
}

/**
 * Service for contact operations with reactive state.
 */
@Injectable({ providedIn: 'root' })
export class ContactsService {
  private api = inject(ApiService);

  // Loading and error state
  loading = signal(false);
  error = signal<string | null>(null);

  // Contact list with refresh trigger
  private refreshList$ = new Subject<void>();

  private contactsResponse = toSignal(
    this.refreshList$.pipe(
      startWith(undefined),
      tap(() => {
        this.loading.set(true);
        this.error.set(null);
      }),
      switchMap(() =>
        this.api.getMany<ApiPersonaListItem>('/api/contacts').pipe(
          tap(() => this.loading.set(false)),
          catchError(err => {
            this.loading.set(false);
            this.error.set(err.message || 'Failed to load contacts');
            return of({ columns: [], data: [] });
          })
        )
      )
    )
  );

  /** All contacts (list view - minimal data) */
  contactsList = computed(() => {
    const response = this.contactsResponse();
    if (!response) return [];
    return response.data.map(item => ({
      id: item.id,
      entityName: item.entity_name,
      isCorporate: item.is_corporate,
      organization: item.organization ?? '',
      primaryEmail: item.primary_email ?? '',
      primaryPhone: item.primary_phone ?? '',
    }));
  });

  /** Trigger a refresh of the contact list */
  refreshContacts(): void {
    this.refreshList$.next();
  }

  /** Get a single contact by ID with all bits */
  async getById(id: string): Promise<Persona> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const response = await this.api
        .getOne<ApiPersona>(`/api/contacts/${id}`)
        .toPromise();
      this.loading.set(false);
      return transformPersona(response!.data);
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to load contact';
      this.error.set(message);
      throw err;
    }
  }

  /** Create a new contact */
  async create(persona: Persona): Promise<Persona> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const response = await this.api
        .create<ApiPersona, PersonaCreate>('/api/contacts', toPersonaCreate(persona))
        .toPromise();
      this.loading.set(false);
      this.refreshContacts();
      return transformPersona(response!.data);
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to create contact';
      this.error.set(message);
      throw err;
    }
  }

  /** Update an existing contact */
  async update(id: string, changes: Partial<Persona>): Promise<Persona> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const response = await this.api
        .update<ApiPersona, PersonaUpdate>(`/api/contacts/${id}`, toPersonaUpdate(changes))
        .toPromise();
      this.loading.set(false);
      this.refreshContacts();
      return transformPersona(response!.data);
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to update contact';
      this.error.set(message);
      throw err;
    }
  }

  /** Delete a contact */
  async delete(id: string): Promise<void> {
    this.loading.set(true);
    this.error.set(null);

    try {
      await this.api.delete(`/api/contacts/${id}`).toPromise();
      this.loading.set(false);
      this.refreshContacts();
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to delete contact';
      this.error.set(message);
      throw err;
    }
  }

  /** Get a single contact bit by ID */
  async getBit(contactId: string, bitId: string): Promise<ContactBit> {
    try {
      const response = await this.api
        .getOne<ApiBit>(`/api/contacts/${contactId}/bits/${bitId}`)
        .toPromise();
      return transformBit(response!.data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load contact info';
      this.error.set(message);
      throw err;
    }
  }

  /** Add a contact bit */
  async addBit(contactId: string, bit: ContactBit, password?: string): Promise<Persona> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const createData = toBitCreate(bit);
      // Add password for URL bits if provided
      if (password && bit.bitType === 'url') {
        createData.password = password;
      }

      const response = await this.api
        .create<ApiPersona, BitCreate>(`/api/contacts/${contactId}/bits`, createData)
        .toPromise();
      this.loading.set(false);
      return transformPersona(response!.data);
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to add contact info';
      this.error.set(message);
      throw err;
    }
  }

  /** Update a contact bit */
  async updateBit(
    contactId: string,
    bitId: string,
    changes: Partial<ContactBit>
  ): Promise<Persona> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const response = await this.api
        .update<ApiPersona, BitUpdate>(
          `/api/contacts/${contactId}/bits/${bitId}`,
          toBitUpdate(changes)
        )
        .toPromise();
      this.loading.set(false);
      return transformPersona(response!.data);
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to update contact info';
      this.error.set(message);
      throw err;
    }
  }

  /** Delete a contact bit */
  async deleteBit(contactId: string, bitId: string): Promise<void> {
    this.loading.set(true);
    this.error.set(null);

    try {
      await this.api.delete(`/api/contacts/${contactId}/bits/${bitId}`).toPromise();
      this.loading.set(false);
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to delete contact info';
      this.error.set(message);
      throw err;
    }
  }

  /** Get decrypted password for a URL bit */
  async getPassword(contactId: string, bitId: string): Promise<string> {
    try {
      const response = await this.api
        .getOne<{ password: string }>(`/api/contacts/${contactId}/bits/${bitId}/password`)
        .toPromise();
      return response!.data.password;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to retrieve password';
      this.error.set(message);
      throw err;
    }
  }

  /** Reorder contact bits */
  async reorderBits(
    contactId: string,
    items: { id: string; bitSequence: number }[]
  ): Promise<Persona> {
    this.loading.set(true);
    this.error.set(null);

    try {
      const response = await this.api
        .create<ApiPersona, BitReorderRequest>(`/api/contacts/${contactId}/bits/reorder`, {
          items: items.map(i => ({ id: i.id, bit_sequence: i.bitSequence })),
        })
        .toPromise();
      this.loading.set(false);
      return transformPersona(response!.data);
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to reorder contact info';
      this.error.set(message);
      throw err;
    }
  }
}
