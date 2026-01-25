import { Component, inject } from '@angular/core';
import { AccountService } from '../services/account.service';

@Component({
  selector: 'app-accounts-list',
  templateUrl: './accounts-list.component.html',
  styleUrl: './accounts-list.component.scss',
})
export class AccountsListComponent {
  private service = inject(AccountService);

  accounts = this.service.accounts;
  columns = this.service.columns;
}
