import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from '@core/api/api.service';
import { MultiRowResponse } from '@core/api/api.types';
import { BalanceSheetRow, ProfitLossRow } from './report.models';

@Injectable({ providedIn: 'root' })
export class ReportService {
  private api = inject(ApiService);

  currentBalanceAccounts(d: string): Observable<MultiRowResponse<BalanceSheetRow>> {
    return this.api.getMany<BalanceSheetRow>('/api/reports/current-balance-accounts', { d });
  }

  profitAndLoss(d1: string, d2: string): Observable<MultiRowResponse<ProfitLossRow>> {
    return this.api.getMany<ProfitLossRow>('/api/reports/profit-loss', { d1, d2 });
  }
}
