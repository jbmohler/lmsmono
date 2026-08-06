import { ItemRef } from '@core/api/api.types';

export interface BalanceSheetRow {
  atype_id: string;
  atype_name: string;
  atype_sort: number;
  debit_account: boolean;
  journal: ItemRef;
  id: string;
  acc_name: string;
  description: string;
  balance: number | null;
}

export interface AccountTypeGroup<T extends BalanceSheetRow | ProfitLossRow = BalanceSheetRow> {
  atype_id: string;
  atype_name: string;
  debit_account: boolean;
  accounts: T[];
  subtotal: number;
}

export interface ProfitLossRow {
  atype_id: string;
  atype_name: string;
  atype_sort: number;
  debit_account: boolean;
  journal: ItemRef;
  id: string;
  acc_name: string;
  description: string;
  amount: number | null;
}

export interface ProfitLossTransactionRow {
  atype_id: string;
  atype_name: string;
  atype_sort: number;
  debit_account: boolean;
  account_id: string;
  acc_name: string;
  journal: ItemRef;
  id: string;
  trandate: string;
  payee: string | null;
  memo: string | null;
  amount: number | null;
}

export interface ProfitLossTransactionGroup {
  atype_id: string;
  atype_name: string;
  debit_account: boolean;
  rows: ProfitLossTransactionRow[];
  subtotal: number;
}

export interface MultiPeriodBalanceSheetRow {
  atype_id: string;
  atype_name: string;
  atype_sort: number;
  debit_account: boolean;
  journal: ItemRef;
  id: string;
  acc_name: string;
  description: string;
  balances: number[];
}

export interface MultiPeriodBalanceSheetResponse {
  periods: string[];
  data: MultiPeriodBalanceSheetRow[];
}

export interface MultiPeriodAccountTypeGroup {
  atype_id: string;
  atype_name: string;
  debit_account: boolean;
  accounts: MultiPeriodBalanceSheetRow[];
  subtotals: number[];
}

/** One rolling window of a multi-period profit & loss report. */
export interface ProfitLossPeriod {
  /** Ending month, e.g. "Jun 2026". */
  label: string;
  d1: string;
  d2: string;
}

export interface MultiPeriodProfitLossAccount {
  id: string;
  acc_name: string;
  description: string;
  journal: ItemRef;
  /** One amount per period, aligned with the report's period list. */
  amounts: number[];
}

export interface MultiPeriodProfitLossGroup {
  atype_id: string;
  atype_name: string;
  atype_sort: number;
  debit_account: boolean;
  accounts: MultiPeriodProfitLossAccount[];
  subtotals: number[];
}

export interface PayeeSummaryRow {
  payee: string | null;
  debit: number;
  items: string[];
}

export interface PayeeSummaryResponse {
  account_name: string;
  date1: string;
  date2: string;
  debit_account: boolean;
  data: PayeeSummaryRow[];
}

export interface AccountRunningBalanceRow {
  tid: string | null;
  trandate: string;
  reference: string | null;
  payee: string | null;
  memo: string | null;
  amount: number | null;
  balance: number | null;
  is_speculative: boolean;
}
