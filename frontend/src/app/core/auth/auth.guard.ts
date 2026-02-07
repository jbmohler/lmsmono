import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  // Already initialized - just check login state synchronously
  if (auth.initialized()) {
    return auth.isLoggedIn() || router.createUrlTree(['/login']);
  }

  // First run - check session from cookie, then verify login
  return auth.checkSession().pipe(
    map(() => auth.isLoggedIn() || router.createUrlTree(['/login']))
  );
};
