import { Component, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';

@Component({
  selector: 'app-contact-detail',
  templateUrl: './contact-detail.component.html',
  styleUrl: './contact-detail.component.scss',
  imports: [RouterLink],
})
export class ContactDetailComponent {
  private route = inject(ActivatedRoute);

  contactId = toSignal(this.route.paramMap.pipe(map(params => params.get('contactId') ?? 'none')));
}
