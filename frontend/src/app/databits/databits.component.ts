import {
  Component,
  signal,
  computed,
  viewChild,
  ElementRef,
  afterNextRender,
  inject,
  effect,
  ChangeDetectionStrategy
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { DataBitsService } from './services/databits.service';
import { DataBitDetailComponent } from './databit-detail/databit-detail.component';
import { DataBit, DataBitListItem } from './databits.model';

@Component({
  selector: 'app-databits',
  templateUrl: './databits.component.html',
  styleUrl: './databits.component.scss',
  imports: [FormsModule, DataBitDetailComponent],
  changeDetection: ChangeDetectionStrategy.Eager,
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class DatabitsComponent {
  private databitsService = inject(DataBitsService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');

  searchQuery = signal('');
  selectedBitId = signal<string | null>(null);
  creatingNew = signal(false);
  mobileShowDetail = signal(false);

  bits = this.databitsService.bitsList;
  loading = this.databitsService.loading;
  error = this.databitsService.error;

  /** Term behind the current results; empty until a search has been run. */
  appliedSearch = this.databitsService.appliedSearch;

  /** Whether the current list came from a request at all. */
  listLoaded = this.databitsService.listLoaded;

  /** Last search term the detail pane was reconciled against. */
  private lastReconciledSearch: string | null = null;

  activeDetailId = computed(() => (this.creatingNew() ? null : this.selectedBitId()));
  showDetail = computed(() => this.creatingNew() || !!this.selectedBitId());

  constructor() {
    afterNextRender(() => {
      this.searchInput()?.nativeElement.focus();
    });

    effect(() => {
      this.databitsService.search.set(this.searchQuery());
    });

    // Keep the detail pane consistent with the search results: if the open
    // data bit is not among them, fall back to the first match (or nothing).
    effect(() => {
      const list = this.bits();
      const term = this.appliedSearch();

      // No search run yet (or the request failed) - the empty list is not a
      // statement about the open bit, so leave the selection alone.
      if (!term) {
        this.lastReconciledSearch = null;
        return;
      }
      // Only reconcile when the search itself changed. A plain list refresh
      // (after a save) must not kick the user off the record they just edited.
      if (term === this.lastReconciledSearch) return;
      this.lastReconciledSearch = term;

      if (this.creatingNew()) return;

      const id = this.selectedBitId();
      if (!id) return;
      if (list.some(b => b.id === id)) return;

      const next = list.length > 0 ? list[0] : null;
      this.selectedBitId.set(next?.id ?? null);
      // Don't force the mobile detail pane open just because results changed.
      if (!next) this.mobileShowDetail.set(false);
      void this.router.navigate([], {
        queryParams: next ? { id: next.id } : {},
        replaceUrl: true,
      });
    });

    const initialId = this.route.snapshot.queryParamMap.get('id');
    if (initialId) {
      this.selectedBitId.set(initialId);
      this.mobileShowDetail.set(true);
    }
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.ctrlKey && event.shiftKey && event.key === 'N') {
      event.preventDefault();
      this.createNew();
      return;
    }

    const target = event.target as HTMLElement;
    const isSearchFocused = target === this.searchInput()?.nativeElement;
    const isInInput =
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.tagName === 'SELECT' ||
      target.isContentEditable;

    if (event.key === 's' && !event.ctrlKey && !event.altKey && !event.metaKey && !isInInput) {
      event.preventDefault();
      this.searchInput()?.nativeElement.focus();
      return;
    }

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (!isInInput || isSearchFocused) {
        event.preventDefault();
        this.navigateList(event.key === 'ArrowDown' ? 1 : -1);
      }
    }

    if (event.key === 'Enter' && isSearchFocused && !this.searchQuery().trim()) {
      // Enter on an empty search box explicitly lists everything (up to the
      // API's page cap) instead of leaving the search-first empty state.
      event.preventDefault();
      this.databitsService.listAll();
    }
  }

  navigateList(direction: number): void {
    const list = this.bits();
    if (list.length === 0) return;
    const currentId = this.selectedBitId();
    const currentIndex = currentId ? list.findIndex(b => b.id === currentId) : -1;
    let newIndex = currentIndex + direction;
    if (newIndex < 0) newIndex = list.length - 1;
    if (newIndex >= list.length) newIndex = 0;
    this.selectBit(list[newIndex]);
  }

  selectBit(bit: DataBitListItem): void {
    this.creatingNew.set(false);
    this.selectedBitId.set(bit.id);
    this.mobileShowDetail.set(true);
    void this.router.navigate([], { queryParams: { id: bit.id }, replaceUrl: true });
  }

  createNew(): void {
    this.selectedBitId.set(null);
    this.creatingNew.set(true);
    this.mobileShowDetail.set(true);
    void this.router.navigate([], { queryParams: {}, replaceUrl: true });
  }

  onBitSaved(bit: DataBit): void {
    this.creatingNew.set(false);
    this.selectedBitId.set(bit.id);
    void this.router.navigate([], { queryParams: { id: bit.id }, replaceUrl: true });
  }

  onBitDeleted(): void {
    this.selectedBitId.set(null);
    this.creatingNew.set(false);
    this.mobileShowDetail.set(false);
    void this.router.navigate([], { queryParams: {}, replaceUrl: true });
  }

  onBack(): void {
    this.creatingNew.set(false);
    this.mobileShowDetail.set(false);
  }

  trackById(_index: number, bit: DataBitListItem): string {
    return bit.id;
  }
}
