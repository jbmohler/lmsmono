import { Injectable, inject } from '@angular/core';

import { ApiService } from '@core/api/api.service';
import { MultiRowResponse } from '@core/api/api.types';
import {
  TemplateSearchResult,
  Transaction,
  TransactionCreate,
  TransactionDetail,
  TransactionFilters,
  TransactionUpdate,
} from '@finances/models/transaction.model';
import { Observable } from 'rxjs';

/**
 * Service for transaction CRUD operations.
 * List filtering is managed locally by each consumer.
 */
@Injectable({ providedIn: 'root' })
export class TransactionService {
  private api = inject(ApiService);

  /** Fetch transactions with the given filters */
  list(filters: TransactionFilters): Observable<MultiRowResponse<Transaction>> {
    return this.api.getMany<Transaction>('/api/transactions', {
      q: filters.q,
      account_id: filters.account_id,
      from: filters.from,
      to: filters.to,
    });
  }

  /** Get a single transaction by ID with its splits */
  getById(id: string) {
    return this.api.getOne<TransactionDetail>(`/api/transactions/${id}`);
  }

  /** Create a new transaction with splits */
  create(data: TransactionCreate) {
    return this.api.create<TransactionDetail, TransactionCreate>('/api/transactions', data);
  }

  /** Update an existing transaction */
  update(id: string, data: TransactionUpdate) {
    return this.api.update<TransactionDetail, TransactionUpdate>(
      `/api/transactions/${id}`,
      data
    );
  }

  /** Delete a transaction */
  delete(id: string) {
    return this.api.delete(`/api/transactions/${id}`);
  }

  /** Search for a transaction template to auto-fill new transactions */
  searchTemplate(query: string) {
    return this.api.getOne<TemplateSearchResult | null>(
      `/api/transactions/template-search`,
      { q: query }
    );
  }
}
