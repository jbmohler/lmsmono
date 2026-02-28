import {
  Component,
  input,
  output,
  signal,
  computed,
  inject,
  viewChild,
  ElementRef,
  afterNextRender,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ContactsService } from '../services/contacts.service';
import { UsersService, UserSearchResult } from '@core/services/users.service';
import { PersonaShare } from '../contacts.model';

@Component({
  selector: 'app-sharing-dialog',
  templateUrl: './sharing-dialog.component.html',
  styleUrl: './sharing-dialog.component.scss',
  imports: [FormsModule],
})
export class SharingDialogComponent {
  private contactsService = inject(ContactsService);
  private usersService = inject(UsersService);

  contactId = input.required<string>();
  isOwner = input<boolean>(true);

  closed = output<void>();
  sharesChanged = output<void>();

  dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');

  loading = signal(false);
  shares = signal<PersonaShare[]>([]);

  // User search
  searchQuery = signal('');
  searchResults = signal<UserSearchResult[]>([]);
  searching = signal(false);

  owner = computed(() => this.shares().find(s => s.isOwner));
  sharedUsers = computed(() => this.shares().filter(s => !s.isOwner));

  constructor() {
    afterNextRender(() => {
      this.dialog().nativeElement.showModal();
      this.loadShares();
    });
  }

  close(): void {
    this.dialog().nativeElement.close();
    this.closed.emit();
  }

  async loadShares(): Promise<void> {
    this.loading.set(true);
    try {
      const shares = await this.contactsService.getShares(this.contactId());
      this.shares.set(shares);
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
