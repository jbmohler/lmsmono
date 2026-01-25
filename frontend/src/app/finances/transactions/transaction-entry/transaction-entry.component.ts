import { Component, ElementRef, output, input, viewChild, viewChildren, signal, computed, afterNextRender, inject, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KeyValuePipe } from '@angular/common';
import { AccountService } from '../../services/account.service';
import { TransactionService } from '../../services/transaction.service';
import { SplitInput } from '../../models/transaction.model';

interface TransactionLine {
  id: number;
  accountId: string;
  debit: number | null;
  credit: number | null;
}

@Component({
  selector: 'app-transaction-entry',
  templateUrl: './transaction-entry.component.html',
  styleUrl: './transaction-entry.component.scss',
  imports: [FormsModule, KeyValuePipe],
})
export class TransactionEntryComponent {
  private accountService = inject(AccountService);
  private transactionService = inject(TransactionService);

  /** Initial date for new transactions */
  initialDate = input<string>();

  /** Transaction ID for editing existing transactions */
  transactionId = input<string>();

  dialogClose = output<void>();
  dialogSave = output<void>();

  dialog = viewChild<ElementRef<HTMLDialogElement>>('dialog');
  dateInput = viewChild<ElementRef<HTMLInputElement>>('dateInput');
  lineInputs = viewChildren<ElementRef<HTMLInputElement | HTMLSelectElement>>('lineInput');

  // Edit mode flag
  isEditMode = computed(() => !!this.transactionId());

  // Header fields
  date = signal(this.todayString());
  reference = signal('');
  payee = signal('');
  memo = signal('');

  // Loading and saving state
  loading = signal(false);
  saving = signal(false);
  errorMessage = signal<string | null>(null);

  // Line items
  private nextLineId = 1;
  lines = signal<TransactionLine[]>([
    { id: this.nextLineId++, accountId: '', debit: null, credit: null },
    { id: this.nextLineId++, accountId: '', debit: null, credit: null },
  ]);

  // Accounts from service, grouped by type
  accountsByType = this.accountService.accountsByType;

  // Computed totals
  totalDebits = computed(() => {
    return this.lines().reduce((sum, line) => sum + (line.debit || 0), 0);
  });

  totalCredits = computed(() => {
    return this.lines().reduce((sum, line) => sum + (line.credit || 0), 0);
  });

  isBalanced = computed(() => {
    const debits = this.totalDebits();
    const credits = this.totalCredits();
    return debits > 0 && Math.abs(debits - credits) < 0.01;
  });

  balanceDifference = computed(() => {
    return Math.abs(this.totalDebits() - this.totalCredits());
  });

  constructor() {
    // Load transaction data when transactionId changes
    effect(() => {
      const id = this.transactionId();
      if (id) {
        this.loadTransaction(id);
      }
    });

    // Set initial date from input if provided, then open dialog
    afterNextRender(() => {
      const initial = this.initialDate();
      if (initial && !this.transactionId()) {
        this.date.set(initial);
      }
      this.dialog()?.nativeElement.showModal();
      this.dateInput()?.nativeElement.focus();
    });
  }

  private loadTransaction(id: string): void {
    this.loading.set(true);
    this.errorMessage.set(null);

    this.transactionService.getById(id).subscribe({
      next: (response) => {
        const txn = response.data;
        this.date.set(txn.trandate);
        this.reference.set(txn.tranref || '');
        this.payee.set(txn.payee || '');
        this.memo.set(txn.memo || '');

        // Convert splits to lines
        const newLines: TransactionLine[] = txn.splits.map((split) => ({
          id: this.nextLineId++,
          accountId: split.account.id,
          debit: split.debit,
          credit: split.credit,
        }));
        this.lines.set(newLines);
        this.loading.set(false);
      },
      error: (err) => {
        this.loading.set(false);
        this.errorMessage.set(err.message || 'Failed to load transaction');
      },
    });
  }

  close(): void {
    this.dialog()?.nativeElement.close();
    // Native close event will emit dialogClose
  }

  handleKeydown(event: KeyboardEvent): void {
    // Ctrl+S - save
    if (event.ctrlKey && event.key === 's') {
      event.preventDefault();
      this.onSave();
      return;
    }

    // Ctrl+Enter - add new line
    if (event.ctrlKey && event.key === 'Enter') {
      event.preventDefault();
      this.addLine();
      return;
    }

    // Ctrl+Backspace - delete current line (if in line area)
    if (event.ctrlKey && event.key === 'Backspace') {
      const target = event.target as HTMLElement;
      const row = target.closest('tr[data-line-id]');
      if (row) {
        const lineId = parseInt(row.getAttribute('data-line-id') || '0', 10);
        if (lineId && this.lines().length > 2) {
          event.preventDefault();
          this.removeLine(lineId);
        }
      }
      return;
    }

    // Tab from last cell of last row - add new line
    if (event.key === 'Tab' && !event.shiftKey) {
      const target = event.target as HTMLElement;
      const row = target.closest('tr[data-line-id]');
      if (row) {
        const lineId = parseInt(row.getAttribute('data-line-id') || '0', 10);
        const lines = this.lines();
        const isLastRow = lines[lines.length - 1]?.id === lineId;
        const isLastCell = target.classList.contains('credit-input');

        if (isLastRow && isLastCell) {
          event.preventDefault();
          this.addLine();
        }
      }
    }
  }

  addLine(): void {
    this.lines.update(lines => [
      ...lines,
      { id: this.nextLineId++, accountId: '', debit: null, credit: null },
    ]);

    // Focus new line's account select after render
    afterNextRender(() => {
      const inputs = this.lineInputs();
      const newLineFirstInput = inputs[inputs.length - 3]; // account select of new row
      newLineFirstInput?.nativeElement?.focus();
    });
  }

  removeLine(lineId: number): void {
    if (this.lines().length <= 2) return; // Keep minimum 2 lines

    const currentLines = this.lines();
    const index = currentLines.findIndex(l => l.id === lineId);

    this.lines.update(lines => lines.filter(l => l.id !== lineId));

    // Focus previous line's account or first line if removing first
    afterNextRender(() => {
      const inputs = this.lineInputs();
      const targetIndex = Math.max(0, (index - 1)) * 3;
      inputs[targetIndex]?.nativeElement?.focus();
    });
  }

  updateLine(lineId: number, field: 'accountId' | 'debit' | 'credit', value: string | number | null): void {
    this.lines.update(lines =>
      lines.map(line => {
        if (line.id !== lineId) return line;

        if (field === 'accountId') {
          return { ...line, accountId: value as string };
        } else if (field === 'debit') {
          // Clear credit if entering debit
          const debit = value === '' || value === null ? null : parseFloat(value as string) || null;
          return { ...line, debit, credit: debit ? null : line.credit };
        } else {
          // Clear debit if entering credit
          const credit = value === '' || value === null ? null : parseFloat(value as string) || null;
          return { ...line, credit, debit: credit ? null : line.debit };
        }
      })
    );
  }

  onSave(): void {
    if (!this.isBalanced() || this.saving()) return;

    this.saving.set(true);
    this.errorMessage.set(null);

    const splits: SplitInput[] = this.lines()
      .filter((line) => line.accountId && (line.debit || line.credit))
      .map((line) => ({
        account_id: line.accountId,
        debit: line.debit ?? undefined,
        credit: line.credit ?? undefined,
      }));

    const id = this.transactionId();
    const request$ = id
      ? this.transactionService.update(id, {
          trandate: this.date(),
          tranref: this.reference() || null,
          payee: this.payee() || null,
          memo: this.memo() || null,
          splits,
        })
      : this.transactionService.create({
          trandate: this.date(),
          tranref: this.reference() || undefined,
          payee: this.payee() || undefined,
          memo: this.memo() || undefined,
          splits,
        });

    request$.subscribe({
      next: () => {
        this.saving.set(false);
        this.dialogSave.emit();
        this.close();
      },
      error: (err) => {
        this.saving.set(false);
        this.errorMessage.set(err.message || 'Failed to save transaction');
      },
    });
  }

  onCancel(): void {
    this.close();
  }

  trackByLineId(_index: number, line: TransactionLine): number {
    return line.id;
  }

  private todayString(): string {
    const d = new Date();
    return d.toISOString().split('T')[0];
  }

  formatCurrency(value: number): string {
    return value.toFixed(2);
  }

  /** Format amount for display in input (empty string for null/zero) */
  formatAmount(value: number | null): string {
    if (value === null || value === 0) {
      return '';
    }
    return value.toFixed(2);
  }

  /** Reformat input value on blur to ensure 2 decimal places */
  formatOnBlur(event: Event): void {
    const input = event.target as HTMLInputElement;
    const value = parseFloat(input.value);
    if (!isNaN(value) && value > 0) {
      input.value = value.toFixed(2);
    } else if (input.value !== '') {
      input.value = '';
    }
  }
}
