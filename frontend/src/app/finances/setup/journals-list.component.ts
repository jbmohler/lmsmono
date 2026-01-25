import { Component, inject } from '@angular/core';
import { JournalService } from '../services/journal.service';

@Component({
  selector: 'app-journals-list',
  templateUrl: './journals-list.component.html',
  styleUrl: './journals-list.component.scss',
})
export class JournalsListComponent {
  private service = inject(JournalService);

  journals = this.service.journals;
  columns = this.service.columns;
}
