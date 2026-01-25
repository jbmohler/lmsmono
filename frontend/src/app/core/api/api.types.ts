/**
 * Core API type definitions matching backend self-describing responses.
 */

/** Column type identifiers matching backend ColumnMeta.type */
export type ColumnType =
  | 'string'
  | 'number'
  | 'currency'
  | 'date'
  | 'datetime'
  | 'boolean'
  | 'uuid'
  | 'ref';

/** Column metadata for self-describing responses */
export interface ColumnMeta {
  key: string;
  label: string;
  type: ColumnType;
}

/** Foreign key reference structure */
export interface ItemRef {
  id: string;
  name: string;
}

/** Single row response wrapper */
export interface SingleRowResponse<T> {
  columns: ColumnMeta[];
  data: T;
}

/** Multi-row response wrapper */
export interface MultiRowResponse<T> {
  columns: ColumnMeta[];
  data: T[];
}

/** API error response */
export interface ApiError {
  detail: string;
}

/** Type guard to check if a value is an ItemRef */
export function isItemRef(value: unknown): value is ItemRef {
  return (
    typeof value === 'object' &&
    value !== null &&
    'id' in value &&
    'name' in value &&
    typeof (value as ItemRef).id === 'string' &&
    typeof (value as ItemRef).name === 'string'
  );
}
