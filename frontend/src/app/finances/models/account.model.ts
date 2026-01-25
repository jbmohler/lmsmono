import { ItemRef } from '../../core/api/api.types';

/**
 * Account domain models matching backend /api/accounts and /api/account-types endpoints.
 */

/** Account type entity (read-only reference data) */
export interface AccountType {
  id: string;
  atype_name: string;
  description: string | null;
  balance_sheet: boolean;
  debit: boolean;
}

/** Account entity with type and journal refs */
export interface Account {
  id: string;
  acc_name: string;
  description: string | null;
  account_type: ItemRef;
  journal: ItemRef;
}

/** Data for creating a new account */
export interface AccountCreate {
  acc_name: string;
  type_id: string;
  journal_id: string;
  description?: string | null;
}

/** Data for updating an account (only name and description) */
export interface AccountUpdate {
  acc_name?: string;
  description?: string | null;
}

/** Transaction from account's perspective (includes debit/credit for that account) */
export interface AccountTransaction {
  id: string;
  trandate: string;
  tranref: string | null;
  payee: string | null;
  memo: string | null;
  debit: number | null;
  credit: number | null;
}
