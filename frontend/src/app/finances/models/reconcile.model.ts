export interface ReconcileSplit {
  split_id: string;
  trandate: string;
  tranref: string | null;
  payee: string | null;
  memo: string | null;
  debit: number | null;
  credit: number | null;
  is_pending: boolean;
}

export interface ReconcileData {
  account_id: string;
  acc_name: string;
  rec_note: string | null;
  prior_reconciled_balance: number;
  splits: ReconcileSplit[];
}

export interface ToggleResult {
  split_id: string;
  is_pending: boolean;
}

export interface FinalizeResult {
  reconciled_count: number;
}
