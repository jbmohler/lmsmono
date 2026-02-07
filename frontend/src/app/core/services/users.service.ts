import { Injectable, inject } from '@angular/core';

import { ApiService } from '@core/api/api.service';

interface ApiUser {
  id: string;
  username: string;
  full_name: string | null;
}

export interface UserSearchResult {
  id: string;
  username: string;
  fullName: string;
}

@Injectable({ providedIn: 'root' })
export class UsersService {
  private api = inject(ApiService);

  /** Search for users by username or full name */
  async searchUsers(query: string): Promise<UserSearchResult[]> {
    if (!query || query.length < 1) {
      return [];
    }

    const response = await this.api
      .getMany<ApiUser>(`/api/users/search?q=${encodeURIComponent(query)}`)
      .toPromise();

    return (response?.data ?? []).map(u => ({
      id: u.id,
      username: u.username,
      fullName: u.full_name ?? u.username,
    }));
  }
}
