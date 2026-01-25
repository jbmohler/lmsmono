import { Injectable, inject, computed } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Subject } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';

import { ApiService } from '../../core/api/api.service';
import { ColumnMeta } from '../../core/api/api.types';
import {
  Account,
  AccountCreate,
  AccountTransaction,
  AccountType,
  AccountUpdate,
} from '../models/account.model';

/**
 * Service for account and account type operations with reactive state.
 */
@Injectable({ providedIn: 'root' })
export class AccountService {
  private api = inject(ApiService);

  // Account list
  private refreshAccounts$ = new Subject<void>();

  private accountsResponse = toSignal(
    this.refreshAccounts$.pipe(
      startWith(undefined),
      switchMap(() => this.api.getMany<Account>('/api/accounts'))
    )
  );

  /** All accounts */
  accounts = computed(() => this.accountsResponse()?.data ?? []);

  /** Column metadata for accounts */
  columns = computed<ColumnMeta[]>(() => this.accountsResponse()?.columns ?? []);

  // Account types (static reference data)
  private accountTypesResponse = toSignal(
    this.api.getMany<AccountType>('/api/account-types')
  );

  /** All account types */
  accountTypes = computed(() => this.accountTypesResponse()?.data ?? []);

  /** Column metadata for account types */
  accountTypeColumns = computed<ColumnMeta[]>(
    () => this.accountTypesResponse()?.columns ?? []
  );

  /** Accounts grouped by account type name */
  accountsByType = computed(() => {
    const accounts = this.accounts();
    const grouped = new Map<string, Account[]>();

    for (const account of accounts) {
      const typeName = account.account_type.name;
      const group = grouped.get(typeName) ?? [];
      group.push(account);
      grouped.set(typeName, group);
    }

    return grouped;
  });

  /** Trigger a refresh of the account list */
  refreshAccounts(): void {
    this.refreshAccounts$.next();
  }

  /** Get a single account by ID */
  getById(id: string) {
    return this.api.getOne<Account>(`/api/accounts/${id}`);
  }

  /** Get transactions for a specific account */
  getAccountTransactions(accountId: string, limit = 50, offset = 0) {
    return this.api.getMany<AccountTransaction>(
      `/api/accounts/${accountId}/transactions`,
      { limit, offset }
    );
  }

  /** Create a new account */
  create(data: AccountCreate) {
    return this.api.create<Account, AccountCreate>('/api/accounts', data);
  }

  /** Update an existing account */
  update(id: string, data: AccountUpdate) {
    return this.api.update<Account, AccountUpdate>(`/api/accounts/${id}`, data);
  }

  /** Delete an account */
  delete(id: string) {
    return this.api.delete(`/api/accounts/${id}`);
  }
}
