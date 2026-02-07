import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401) {
        // Don't redirect if already on login page or checking session
        const isLoginPage = router.url === '/login';
        const isAuthCheck = req.url.includes('/api/auth/me');

        if (!isLoginPage && !isAuthCheck) {
          router.navigate(['/login']);
        }
      }
      // 403 errors are handled by individual components - they show the error
      // but don't redirect since the user is still authenticated
      return throwError(() => error);
    })
  );
};
