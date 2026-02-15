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
