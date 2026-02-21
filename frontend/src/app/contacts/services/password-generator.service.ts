import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';

interface GeneratePasswordResponse {
  password: string;
  mode: string;
  bits: number;
}

@Injectable({ providedIn: 'root' })
export class PasswordGeneratorService {
  private http = inject(HttpClient);

  generate(mode: string, bits: number): Observable<string> {
    const params = new HttpParams().set('mode', mode).set('bits', String(bits));
    return this.http
      .get<GeneratePasswordResponse>('/api/password/generate', { params })
      .pipe(map((r) => r.password));
  }
}
