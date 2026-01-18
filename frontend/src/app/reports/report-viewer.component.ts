import { Component, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';

@Component({
  selector: 'app-report-viewer',
  templateUrl: './report-viewer.component.html',
  styleUrl: './report-viewer.component.scss',
  imports: [RouterLink],
})
export class ReportViewerComponent {
  private route = inject(ActivatedRoute);

  reportType = toSignal(this.route.paramMap.pipe(map(params => params.get('reportType'))));
}
