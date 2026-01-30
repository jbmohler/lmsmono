import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { ApiError, MultiRowResponse, SingleRowResponse } from './api.types';

/**
 * Base API service providing typed HTTP methods with error handling.
 * Feature services compose this service rather than extending it.
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);

  /** GET single row */
  getOne<T>(
    url: string,
    params?: Record<string, string | number | boolean | undefined>
  ): Observable<SingleRowResponse<T>> {
    let httpParams = new HttpParams();
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== '') {
          httpParams = httpParams.set(key, String(value));
        }
      }
    }
    return this.http
      .get<SingleRowResponse<T>>(url, { params: httpParams })
      .pipe(catchError(this.handleError));
  }

  /** GET multiple rows with optional query params */
  getMany<T>(
    url: string,
    params?: Record<string, string | number | boolean | undefined>
  ): Observable<MultiRowResponse<T>> {
    let httpParams = new HttpParams();
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== '') {
          httpParams = httpParams.set(key, String(value));
        }
      }
    }
    return this.http
      .get<MultiRowResponse<T>>(url, { params: httpParams })
      .pipe(catchError(this.handleError));
  }

  /** POST create */
  create<T, D>(url: string, data: D): Observable<SingleRowResponse<T>> {
    return this.http
      .post<SingleRowResponse<T>>(url, data)
      .pipe(catchError(this.handleError));
  }

  /** PUT update */
  update<T, D>(url: string, data: D): Observable<SingleRowResponse<T>> {
    return this.http
      .put<SingleRowResponse<T>>(url, data)
      .pipe(catchError(this.handleError));
  }

  /** DELETE */
  delete(url: string): Observable<void> {
    return this.http.delete<void>(url).pipe(catchError(this.handleError));
  }

  /** Extract data from single row response */
  extractOne<T>(response: SingleRowResponse<T>): T {
    return response.data;
  }

  /** Extract data array from multi row response */
  extractMany<T>(response: MultiRowResponse<T>): T[] {
    return response.data;
  }

  /** Map single row response to data only */
  mapOne<T>(): (source: Observable<SingleRowResponse<T>>) => Observable<T> {
    return (source) => source.pipe(map((r) => r.data));
  }

  /** Map multi row response to data array only */
  mapMany<T>(): (source: Observable<MultiRowResponse<T>>) => Observable<T[]> {
    return (source) => source.pipe(map((r) => r.data));
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An unexpected error occurred';

    if (error.error && typeof error.error === 'object' && 'detail' in error.error) {
      message = (error.error as ApiError).detail;
    } else if (error.message) {
      message = error.message;
    }

    console.error('API Error:', message, error);
    return throwError(() => new Error(message));
  }
}
