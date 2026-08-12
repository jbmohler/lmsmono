import { Injectable, inject } from '@angular/core';
import { RouterStateSnapshot, TitleStrategy } from '@angular/router';

import { PageTitleService } from './page-title.service';

/** Feeds each route's static `title` into PageTitleService instead of writing
 * document.title directly, so a component-level detail can still layer on top. */
@Injectable({ providedIn: 'root' })
export class AppTitleStrategy extends TitleStrategy {
  private pageTitle = inject(PageTitleService);

  override updateTitle(snapshot: RouterStateSnapshot): void {
    this.pageTitle.setRouteTitle(this.buildTitle(snapshot));
  }
}
