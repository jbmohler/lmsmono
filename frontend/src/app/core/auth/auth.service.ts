import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of, tap } from 'rxjs';
import { LoginRequest, LoginResponse, User } from './auth.types';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private currentUser = signal<User | null>(null);
  private _initialized = signal(false);

  readonly user = this.currentUser.asReadonly();
  readonly isLoggedIn = computed(() => this.currentUser() !== null);
  readonly initialized = this._initialized.asReadonly();
  readonly capabilities = computed(() => new Set(this.currentUser()?.capabilities ?? []));

  login(username: string, password: string): Observable<User> {
    const request: LoginRequest = { username, password };
    return this.http.post<LoginResponse>('/api/auth/login', request).pipe(
      map(response => this.mapResponseToUser(response)),
      tap(user => this.currentUser.set(user))
    );
  }

  logout(): Observable<void> {
    return this.http.post<void>('/api/auth/logout', {}).pipe(
      tap(() => this.currentUser.set(null))
    );
  }

  checkSession(): Observable<User | null> {
    return this.http.get<LoginResponse>('/api/auth/me').pipe(
      map(response => this.mapResponseToUser(response)),
      tap(user => {
        this.currentUser.set(user);
        this._initialized.set(true);
      }),
      catchError(() => {
        this.currentUser.set(null);
        this._initialized.set(true);
        return of(null);
      })
    );
  }

  /**
   * Check capability imperatively (for use in code, not templates).
   * For templates, create a computed signal in your component:
   *   canWrite = computed(() => this.auth.capabilities().has('contacts:write'));
   */
  hasCapability(capability: string): boolean {
    return this.capabilities().has(capability);
  }

  private mapResponseToUser(response: LoginResponse): User {
    return {
      id: response.id,
      username: response.username,
      fullName: response.full_name,
      capabilities: response.capabilities,
    };
  }
}
