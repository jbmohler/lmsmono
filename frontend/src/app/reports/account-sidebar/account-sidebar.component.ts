import { Component, input, output, inject, signal, effect } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '@core/api/api.service';
import { AccountService } from '@finances/services/account.service';
import { AccountDetail, AccountTransaction } from '@finances/models/account.model';
import { PersonaListItem } from '../../contacts/contacts.model';

interface ApiPersonaListItem {
  id: string;
  entity_name: string;
  is_corporate: boolean;
  organization: string | null;
  primary_email: string | null;
  primary_phone: string | null;
  is_owner: boolean;
}

type Tab = 'info' | 'contacts' | 'transactions';

@Component({
  selector: 'app-account-sidebar',
  templateUrl: './account-sidebar.component.html',
  styleUrl: './account-sidebar.component.scss',
  imports: [CurrencyPipe, DatePipe, RouterLink],
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class AccountSidebarComponent {
  private api = inject(ApiService);
  private accountService = inject(AccountService);

  accountId = input.required<string>();
  sidebarClose = output<void>();
  transactionOpen = output<string>();
  accountEdit = output<string>();

  activeTab = signal<Tab>('info');
  account = signal<AccountDetail | null>(null);
  contacts = signal<PersonaListItem[]>([]);
  transactions = signal<AccountTransaction[]>([]);
  contactsLoaded = signal(false);
  transactionsLoaded = signal(false);

  constructor() {
    effect(() => {
      const id = this.accountId();
      this.activeTab.set('info');
      this.contacts.set([]);
      this.transactions.set([]);
      this.contactsLoaded.set(false);
      this.transactionsLoaded.set(false);
      this.account.set(null);
      this.loadAccount(id);
    });
  }

  setTab(tab: Tab): void {
    this.activeTab.set(tab);
    if (tab === 'contacts' && !this.contactsLoaded()) {
      this.loadContacts();
    }
    if (tab === 'transactions' && !this.transactionsLoaded()) {
      this.loadTransactions();
    }
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      this.sidebarClose.emit();
    }
  }

  private loadAccount(id: string): void {
    this.accountService.getById(id).subscribe((resp) => {
      this.account.set(resp.data);
    });
  }

  private loadContacts(): void {
    const keywords = this.account()?.contact_keywords;
    if (!keywords) {
      this.contactsLoaded.set(true);
      return;
    }
    this.api
      .getMany<ApiPersonaListItem>('/api/contacts', { search: keywords })
      .subscribe((resp) => {
        this.contacts.set(resp.data.map(item => ({
          id: item.id,
          entityName: item.entity_name,
          isCorporate: item.is_corporate,
          organization: item.organization ?? '',
          primaryEmail: item.primary_email ?? '',
          primaryPhone: item.primary_phone ?? '',
          isOwner: item.is_owner,
        })));
        this.contactsLoaded.set(true);
      });
  }

  private loadTransactions(): void {
    const id = this.accountId();
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    const from = oneYearAgo.toISOString().slice(0, 10);
    this.accountService
      .getAccountTransactions(id, 200, 0, from)
      .subscribe((resp) => {
        this.transactions.set(resp.data);
        this.transactionsLoaded.set(true);
      });
  }
}
