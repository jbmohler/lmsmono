import { HttpInterceptorFn, HttpErrorResponse, HttpClient } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, finalize, shareReplay, switchMap, throwError } from 'rxjs';

// A single in-flight refresh is shared across all requests that 401 at once, so
// a burst of concurrent calls triggers exactly one device-token rotation rather
// than racing each other into invalidation.
let refreshInFlight: Observable<unknown> | null = null;

function refreshSession(http: HttpClient): Observable<unknown> {
  if (!refreshInFlight) {
    refreshInFlight = http.post('/api/auth/refresh', {}).pipe(
      finalize(() => {
        refreshInFlight = null;
      }),
      shareReplay(1)
    );
  }
  return refreshInFlight;
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const http = inject(HttpClient);

  // The auth endpoints themselves must never trigger a refresh attempt, or a
  // failing refresh/login would recurse.
  const isAuthEndpoint =
    req.url.includes('/api/auth/refresh') ||
    req.url.includes('/api/auth/login') ||
    req.url.includes('/api/auth/logout');

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status !== 401 || isAuthEndpoint) {
        // 403 errors are handled by individual components - they show the error
        // but don't redirect since the user is still authenticated.
        return throwError(() => error);
      }

      // The session check on app load is allowed to fail quietly (no redirect);
      // any other request should land on the login page if we cannot recover.
      const isAuthCheck = req.url.includes('/api/auth/me');

      // A 401 may just mean the short-lived session lapsed. Try to mint a fresh
      // session from the remember-me device token, then replay the request.
      return refreshSession(http).pipe(
        switchMap(() => next(req)),
        catchError(() => {
          if (!isAuthCheck && router.url !== '/login') {
            router.navigate(['/login']);
          }
          return throwError(() => error);
        })
      );
    })
  );
};
