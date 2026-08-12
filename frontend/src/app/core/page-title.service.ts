import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { Title } from '@angular/platform-browser';

const APP_NAME = 'LMS';

/**
 * Drives the browser tab title. The router sets a static base title per route
 * (see AppTitleStrategy); components can layer a specific detail on top of it
 * once their data loads (e.g. an account or contact name). The base title
 * resets on every navigation, so a detail from the previous page never lingers.
 */
@Injectable({ providedIn: 'root' })
export class PageTitleService {
  private titleService = inject(Title);

  private routeTitle = signal<string | undefined>(undefined);
  private detail = signal<string | null>(null);

  private fullTitle = computed(() => {
    const base = this.routeTitle();
    const detail = this.detail();
    const label = base && detail ? `${base}: ${detail}` : (base ?? detail ?? undefined);
    return label ? `${label} - ${APP_NAME}` : APP_NAME;
  });

  constructor() {
    effect(() => {
      this.titleService.setTitle(this.fullTitle());
    });
  }

  /** Called by AppTitleStrategy after each navigation. Clears any stale detail. */
  setRouteTitle(title: string | undefined): void {
    this.routeTitle.set(title);
    this.detail.set(null);
  }

  /** Called by a component to refine the current route title with the specific
   * thing being viewed, e.g. setDetail(accountName) on the reconcile page. Pass
   * null to clear it (e.g. on destroy, so a later page doesn't inherit it). */
  setDetail(detail: string | null): void {
    this.detail.set(detail);
  }
}
