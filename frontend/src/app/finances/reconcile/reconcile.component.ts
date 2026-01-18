import { Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';

@Component({
  selector: 'app-reconcile',
  templateUrl: './reconcile.component.html',
  styleUrl: './reconcile.component.scss',
})
export class ReconcileComponent {
  private route = inject(ActivatedRoute);

  accountId = toSignal(this.route.paramMap.pipe(map(params => params.get('accountId') ?? 'none')));
}
