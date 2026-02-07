import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of, tap } from 'rxjs';
import { LoginRequest, LoginResponse, User } from './auth.types';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private currentUser = signal<User | null>(null);

  readonly user = this.currentUser.asReadonly();
  readonly isLoggedIn = computed(() => this.currentUser() !== null);

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
      tap(user => this.currentUser.set(user)),
      catchError(() => {
        this.currentUser.set(null);
        return of(null);
      })
    );
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
