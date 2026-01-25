import { Component, inject } from '@angular/core';
import { AccountTypeService } from '../services/account-type.service';

@Component({
  selector: 'app-account-types-list',
  templateUrl: './account-types-list.component.html',
  styleUrl: './account-types-list.component.scss',
})
export class AccountTypesListComponent {
  private service = inject(AccountTypeService);

  accountTypes = this.service.accountTypes;
  columns = this.service.columns;
}
