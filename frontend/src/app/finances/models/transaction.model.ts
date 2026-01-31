import { ItemRef } from '@core/api/api.types';

/**
 * Transaction domain models matching backend /api/transactions endpoints.
 */

/** Transaction split (line item) */
export interface TransactionSplit {
  id: string;
  account: ItemRef;
  debit: number | null;
  credit: number | null;
}

/** Transaction header (list view) */
export interface Transaction {
  id: string;
  trandate: string;
  tranref: string | null;
  payee: string | null;
  memo: string | null;
}

/** Transaction with splits (detail view) */
export interface TransactionDetail extends Transaction {
  splits: TransactionSplit[];
}

/** Split data for create/update (account_id instead of ref) */
export interface SplitInput {
  account_id: string;
  debit?: number | null;
  credit?: number | null;
}

/** Data for creating a new transaction */
export interface TransactionCreate {
  trandate: string;
  splits: SplitInput[];
  tranref?: string | null;
  payee?: string | null;
  memo?: string | null;
}

/** Data for updating a transaction */
export interface TransactionUpdate {
  trandate?: string | null;
  tranref?: string | null;
  payee?: string | null;
  memo?: string | null;
  splits?: SplitInput[] | null;
}

/** Filter parameters for listing transactions */
export interface TransactionFilters {
  q?: string;
  account_id?: string;
  from?: string;
  to?: string;
}

/** Template search result for quick-fill feature */
export interface TemplateSearchResult {
  payee: string | null;
  memo: string | null;
  frequency: number;
  splits: TransactionSplit[];
}
