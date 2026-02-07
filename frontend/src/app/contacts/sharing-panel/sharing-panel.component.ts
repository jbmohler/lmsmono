import { Component, input, output, signal, computed, inject, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ContactsService } from '../services/contacts.service';
import { UsersService, UserSearchResult } from '@core/services/users.service';
import { PersonaShare } from '../contacts.model';

@Component({
  selector: 'app-sharing-panel',
  templateUrl: './sharing-panel.component.html',
  styleUrl: './sharing-panel.component.scss',
  imports: [FormsModule],
})
export class SharingPanelComponent {
  private contactsService = inject(ContactsService);
  private usersService = inject(UsersService);

  contactId = input.required<string>();
  isOwner = input<boolean>(true);
  sharesChanged = output<void>();

  expanded = signal(false);
  loading = signal(false);
  shares = signal<PersonaShare[]>([]);
  loaded = signal(false);

  // User search
  searchQuery = signal('');
  searchResults = signal<UserSearchResult[]>([]);
  searching = signal(false);

  owner = computed(() => this.shares().find(s => s.isOwner));
  sharedUsers = computed(() => this.shares().filter(s => !s.isOwner));

  // Summary for collapsed view
  shareSummary = computed(() => {
    const shared = this.sharedUsers();
    if (shared.length === 0) return '';
    if (shared.length === 1) return shared[0].user.name;
    if (shared.length === 2) return `${shared[0].user.name}, ${shared[1].user.name}`;
    return `${shared[0].user.name}, ${shared[1].user.name} +${shared.length - 2}`;
  });

  constructor() {
    // Load shares when contactId changes
    effect(() => {
      const id = this.contactId();
      if (id) {
        this.loaded.set(false);
        this.loadShares();
      }
    });
  }

  toggle(): void {
    this.expanded.set(!this.expanded());
  }

  async loadShares(): Promise<void> {
    this.loading.set(true);
    try {
      const shares = await this.contactsService.getShares(this.contactId());
      this.shares.set(shares);
      this.loaded.set(true);
    } finally {
      this.loading.set(false);
    }
  }

  async onSearchInput(): Promise<void> {
    const query = this.searchQuery().trim();
    if (query.length < 2) {
      this.searchResults.set([]);
      return;
    }

    this.searching.set(true);
    try {
      const results = await this.usersService.searchUsers(query);
      // Filter out users already shared with
      const existingIds = new Set(this.shares().map(s => s.user.id));
      this.searchResults.set(results.filter(r => !existingIds.has(r.id)));
    } finally {
      this.searching.set(false);
    }
  }

  async addShare(user: UserSearchResult): Promise<void> {
    this.loading.set(true);
    try {
      const shares = await this.contactsService.addShare(this.contactId(), user.id);
      this.shares.set(shares);
      this.searchQuery.set('');
      this.searchResults.set([]);
      this.sharesChanged.emit();
    } finally {
      this.loading.set(false);
    }
  }

  async removeShare(userId: string): Promise<void> {
    const confirmed = window.confirm('Remove this user\'s access to this contact?');
    if (!confirmed) return;

    this.loading.set(true);
    try {
      await this.contactsService.removeShare(this.contactId(), userId);
      this.shares.update(shares => shares.filter(s => s.user.id !== userId));
      this.sharesChanged.emit();
    } finally {
      this.loading.set(false);
    }
  }

  async transferOwnership(userId: string): Promise<void> {
    const user = this.shares().find(s => s.user.id === userId);
    const userName = user?.user.name ?? 'this user';
    const confirmed = window.confirm(
      `Transfer ownership to ${userName}? You will become a shared user with read-only access.`
    );
    if (!confirmed) return;

    this.loading.set(true);
    try {
      await this.contactsService.transferOwnership(this.contactId(), userId);
      await this.loadShares();
      this.sharesChanged.emit();
    } finally {
      this.loading.set(false);
    }
  }
}
