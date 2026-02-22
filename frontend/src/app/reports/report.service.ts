import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ApiService } from '@core/api/api.service';
import { MultiRowResponse } from '@core/api/api.types';
import {
  AccountRunningBalanceRow,
  BalanceSheetRow,
  MultiPeriodBalanceSheetResponse,
  ProfitLossRow,
  ProfitLossTransactionRow,
} from './report.models';

@Injectable({ providedIn: 'root' })
export class ReportService {
  private api = inject(ApiService);
  private http = inject(HttpClient);

  currentBalanceAccounts(d: string): Observable<MultiRowResponse<BalanceSheetRow>> {
    return this.api.getMany<BalanceSheetRow>('/api/reports/current-balance-accounts', { d });
  }

  profitAndLoss(d1: string, d2: string): Observable<MultiRowResponse<ProfitLossRow>> {
    return this.api.getMany<ProfitLossRow>('/api/reports/profit-loss', { d1, d2 });
  }

  profitLossTransactions(
    d1: string,
    d2: string,
  ): Observable<MultiRowResponse<ProfitLossTransactionRow>> {
    return this.api.getMany<ProfitLossTransactionRow>('/api/reports/profit-loss-transactions', {
      d1,
      d2,
    });
  }

  accountRunningBalance(accountId: string, d: string): Observable<MultiRowResponse<AccountRunningBalanceRow>> {
    return this.api.getMany<AccountRunningBalanceRow>('/api/reports/account-running-balance', {
      account_id: accountId,
      d,
    });
  }

  multiPeriodBalanceSheet(
    year: number,
    month: number,
    periods: number,
  ): Observable<MultiPeriodBalanceSheetResponse> {
    const params = new HttpParams()
      .set('year', year)
      .set('month', month)
      .set('periods', periods);
    return this.http.get<MultiPeriodBalanceSheetResponse>(
      '/api/reports/multi-period-balance-sheet',
      { params },
    );
  }
}
