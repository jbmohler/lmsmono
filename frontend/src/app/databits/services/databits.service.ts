import { Injectable, inject, computed, signal } from '@angular/core';
import { toSignal, toObservable } from '@angular/core/rxjs-interop';
import { Subject, of, combineLatest } from 'rxjs';
import {
  startWith, switchMap, catchError, tap, filter,
  debounceTime, distinctUntilChanged,
} from 'rxjs/operators';

import { ApiService } from '@core/api/api.service';
import { AuthService } from '@core/auth/auth.service';
import { DataBit, DataBitListItem, DataBitTag } from '../databits.model';

/** Largest page the databits endpoint accepts (Parameter(le=500)). */
const MAX_LIST_LIMIT = 500;

interface ApiDataBitTag {
  id: string;
  name: string;
  description: string;
}

interface ApiDataBit {
  id: string;
  caption: string | null;
  data: string | null;
  website: string | null;
  uname: string | null;
  pword: string | null;
  tags?: ApiDataBitTag[];
}

interface ApiDataBitListItem {
  id: string;
  caption: string | null;
  website: string | null;
  uname: string | null;
}

interface DataBitRequest {
  caption?: string | null;
  data?: string | null;
  website?: string | null;
  uname?: string | null;
  pword?: string | null;
}

function transformBit(api: ApiDataBit): DataBit {
  return {
    id: api.id,
    caption: api.caption ?? '',
    data: api.data ?? '',
    website: api.website ?? '',
    uname: api.uname ?? '',
    pword: api.pword ?? '',
    tags: (api.tags ?? []).map(t => ({ id: t.id, name: t.name, description: t.description })),
  };
}

@Injectable({ providedIn: 'root' })
export class DataBitsService {
  private api = inject(ApiService);
  private auth = inject(AuthService);

  loading = signal(false);
  error = signal<string | null>(null);
  search = signal('');

  /**
   * The search term whose results are currently in the list. Empty means the
   * list is either unloaded or an explicit unfiltered listing — see listLoaded.
   */
  private _appliedSearch = signal('');
  appliedSearch = this._appliedSearch.asReadonly();

  /** Whether the current list came from an actual request. */
  private _listLoaded = signal(false);
  listLoaded = this._listLoaded.asReadonly();

  /**
   * Set by listAll() to load without a search term. Stays set across refreshes
   * so saving does not blank the list, and clears as soon as the term changes.
   */
  private showAll = false;

  private refreshList$ = new Subject<void>();
  private user$ = toObservable(this.auth.user);

  private bitsResponse = toSignal(
    combineLatest([
      this.user$,
      this.refreshList$.pipe(startWith(undefined)),
      toObservable(this.search).pipe(
        debounceTime(300),
        distinctUntilChanged(),
        // Typing a term ends an explicit "list all". Only a non-empty term
        // does so: a debounced empty value can land after the user cleared the
        // box and pressed Enter, and must not cancel that explicit request.
        tap(term => {
          if (term.trim()) this.showAll = false;
        }),
        startWith(this.search())
      ),
    ]).pipe(
      filter(([user]) => user !== null),
      tap(() => {
        this.loading.set(true);
        this.error.set(null);
      }),
      switchMap(([, , search]) => {
        const term = search.trim();
        // Require a search first, unless the user explicitly asked for the
        // full list — never load everything by default.
        if (!term && !this.showAll) {
          this.loading.set(false);
          this._appliedSearch.set('');
          this._listLoaded.set(false);
          return of({ columns: [], data: [] });
        }
        const params = term ? { search: term } : { limit: MAX_LIST_LIMIT };
        return this.api.getMany<ApiDataBitListItem>('/api/databits', params).pipe(
          tap(() => {
            this.loading.set(false);
            this._appliedSearch.set(term);
            this._listLoaded.set(true);
          }),
          catchError(err => {
            this.loading.set(false);
            // Leave appliedSearch empty so a failed request is not mistaken
            // for "no matches" and does not close an open detail.
            this._appliedSearch.set('');
            this._listLoaded.set(false);
            this.error.set(err.message || 'Failed to load data bits');
            return of({ columns: [], data: [] });
          })
        );
      })
    )
  );

  bitsList = computed<DataBitListItem[]>(() => {
    if (!this.auth.user()) return [];
    const response = this.bitsResponse();
    if (!response) return [];
    return response.data.map(item => ({
      id: item.id,
      caption: item.caption ?? '',
      website: item.website ?? '',
      uname: item.uname ?? '',
    }));
  });

  refreshBits(): void {
    this.refreshList$.next();
  }

  /**
   * Explicitly load the full list with no search term, capped at the API's
   * maximum page size. Stays in effect until the search term changes.
   */
  listAll(): void {
    this.showAll = true;
    this.refreshList$.next();
  }

  async getById(id: string): Promise<DataBit> {
    this.error.set(null);
    try {
      const response = await this.api.getOne<ApiDataBit>(`/api/databits/${id}`).toPromise();
      return transformBit(response!.data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load data bit';
      this.error.set(message);
      throw err;
    }
  }

  async create(data: Partial<DataBit>): Promise<DataBit> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const body: DataBitRequest = {
        caption: data.caption || null,
        data: data.data || null,
        website: data.website || null,
        uname: data.uname || null,
        pword: data.pword || null,
      };
      const response = await this.api
        .create<ApiDataBit, DataBitRequest>('/api/databits', body)
        .toPromise();
      this.loading.set(false);
      this.refreshBits();
      return transformBit(response!.data);
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to create data bit';
      this.error.set(message);
      throw err;
    }
  }

  async update(id: string, data: Partial<DataBit>): Promise<DataBit> {
    this.loading.set(true);
    this.error.set(null);
    try {
      const body: DataBitRequest = {};
      if (data.caption !== undefined) body.caption = data.caption || null;
      if (data.data !== undefined) body.data = data.data || null;
      if (data.website !== undefined) body.website = data.website || null;
      if (data.uname !== undefined) body.uname = data.uname || null;
      if (data.pword !== undefined) body.pword = data.pword || null;

      const response = await this.api
        .update<ApiDataBit, DataBitRequest>(`/api/databits/${id}`, body)
        .toPromise();
      this.loading.set(false);
      this.refreshBits();
      return transformBit(response!.data);
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to update data bit';
      this.error.set(message);
      throw err;
    }
  }

  async delete(id: string): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      await this.api.delete(`/api/databits/${id}`).toPromise();
      this.loading.set(false);
      this.refreshBits();
    } catch (err: unknown) {
      this.loading.set(false);
      const message = err instanceof Error ? err.message : 'Failed to delete data bit';
      this.error.set(message);
      throw err;
    }
  }

  // -------------------------------------------------------------------------
  // Tag Methods
  // -------------------------------------------------------------------------

  private _tagList = signal<DataBitTag[] | null>(null);

  /** All databit tags (lazy-loaded, cached for the session). */
  tagList = this._tagList.asReadonly();

  async loadTagList(): Promise<DataBitTag[]> {
    const cached = this._tagList();
    if (cached) return cached;

    try {
      const response = await this.api
        .getMany<ApiDataBitTag>('/api/databits/tags')
        .toPromise();
      const tags = (response?.data ?? []).map(t => ({ id: t.id, name: t.name, description: t.description }));
      this._tagList.set(tags);
      return tags;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load databit tags';
      this.error.set(message);
      throw err;
    }
  }

  /** Add a tag to a data bit. Returns updated tag list. */
  async addBitTag(bitId: string, tagId: string): Promise<DataBitTag[]> {
    try {
      const response = await this.api
        .createMany<ApiDataBitTag, Record<string, never>>(`/api/databits/${bitId}/tags/${tagId}`, {})
        .toPromise();
      return (response?.data ?? []).map(t => ({ id: t.id, name: t.name, description: t.description }));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to add tag';
      this.error.set(message);
      throw err;
    }
  }

  /** Remove a tag from a data bit. Returns updated tag list. */
  async removeBitTag(bitId: string, tagId: string): Promise<DataBitTag[]> {
    try {
      const response = await this.api
        .deleteMany<ApiDataBitTag>(`/api/databits/${bitId}/tags/${tagId}`)
        .toPromise();
      return (response?.data ?? []).map(t => ({ id: t.id, name: t.name, description: t.description }));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to remove tag';
      this.error.set(message);
      throw err;
    }
  }
}
