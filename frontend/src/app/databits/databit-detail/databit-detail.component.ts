import {
  Component,
  input,
  output,
  signal,
  computed,
  inject,
  effect,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DataBitsService } from '../services/databits.service';
import { DataBit, DataBitTag } from '../databits.model';
import { TagSelectorComponent } from '@shared/components/tag-selector/tag-selector.component';

@Component({
  selector: 'app-databit-detail',
  templateUrl: './databit-detail.component.html',
  styleUrl: './databit-detail.component.scss',
  imports: [FormsModule, TagSelectorComponent],
  host: {
    '(keydown)': 'handleKeydown($event)',
  },
})
export class DataBitDetailComponent {
  private databitsService = inject(DataBitsService);

  bitId = input<string | null>(null);
  back = output<void>();
  saved = output<DataBit>();
  deleted = output<void>();

  bit = signal<DataBit | null>(null);
  loading = signal(false);
  isEditing = signal(false);
  editData = signal<Partial<DataBit>>({});
  showPassword = signal(false);
  copied = signal(false);

  isNew = computed(() => !this.bitId());

  allTags = this.databitsService.tagList;
  localBitTags = signal<DataBitTag[]>([]);
  bitTagIds = computed(() => this.localBitTags().map(t => t.id));
  showTagPopover = signal(false);
  sortedBitTags = computed(() =>
    [...this.localBitTags()].sort((a, b) => a.name.localeCompare(b.name))
  );

  constructor() {
    effect(() => {
      const id = this.bitId();
      if (id) {
        this.showPassword.set(false);
        void this.load(id);
      } else {
        this.bit.set(null);
        this.localBitTags.set([]);
        this.editData.set({ caption: '', data: '', website: '', uname: '', pword: '' });
        this.isEditing.set(true);
      }
    });
    void this.databitsService.loadTagList();
  }

  private async load(id: string): Promise<void> {
    this.loading.set(true);
    try {
      const bit = await this.databitsService.getById(id);
      if (this.bitId() === id) {
        this.bit.set(bit);
        this.localBitTags.set(bit.tags ?? []);
        this.isEditing.set(false);
      }
    } catch {
      // error handled by service
    } finally {
      this.loading.set(false);
    }
  }

  async onTagToggled(event: { tagIds: string[]; action: 'add' | 'remove' }): Promise<void> {
    const id = this.bitId();
    if (!id) return;
    try {
      let updatedTags: DataBitTag[] = this.localBitTags();
      if (event.action === 'add') {
        updatedTags = await this.databitsService.addBitTag(id, event.tagIds[0]);
      } else {
        for (const tagId of event.tagIds) {
          updatedTags = await this.databitsService.removeBitTag(id, tagId);
        }
      }
      this.localBitTags.set(updatedTags);
    } catch {
      // error handled by service
    }
  }

  enterEditMode(): void {
    const bit = this.bit();
    if (!bit) return;
    this.editData.set({ ...bit });
    this.isEditing.set(true);
  }

  cancelEdit(): void {
    if (this.isNew()) {
      this.back.emit();
    } else {
      this.isEditing.set(false);
      this.editData.set({});
    }
  }

  async saveEdit(): Promise<void> {
    const data = this.editData();
    const id = this.bitId();
    try {
      if (id) {
        const updated = await this.databitsService.update(id, data);
        this.bit.set(updated);
        this.saved.emit(updated);
        this.isEditing.set(false);
        this.editData.set({});
      } else {
        const created = await this.databitsService.create(data);
        this.saved.emit(created);
      }
    } catch {
      // error handled by service
    }
  }

  updateField(field: keyof DataBit, value: string): void {
    this.editData.update(d => ({ ...d, [field]: value }));
  }

  async confirmDelete(): Promise<void> {
    const id = this.bitId();
    if (!id) return;
    if (!confirm('Delete this data bit?')) return;
    try {
      await this.databitsService.delete(id);
      this.deleted.emit();
    } catch {
      // error handled by service
    }
  }

  async copyPassword(): Promise<void> {
    const pword = this.bit()?.pword;
    if (!pword) return;
    await navigator.clipboard.writeText(pword);
    this.copied.set(true);
    setTimeout(() => this.copied.set(false), 2000);
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && this.isEditing()) {
      event.preventDefault();
      this.cancelEdit();
    }
    if (event.ctrlKey && event.key === 's' && this.isEditing()) {
      event.preventDefault();
      void this.saveEdit();
    }
  }
}
