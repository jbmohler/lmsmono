# Frontend Development Guidelines

## Angular Patterns

### Signals and Reactivity

**Always use `toSignal` for HTTP observables** - never use the subscribe + signal.set pattern:

```typescript
// BAD - Don't do this
health = signal<HealthResponse | null>(null);
loadHealth() {
  this.http.get<HealthResponse>('/api/health').subscribe({
    next: (response) => this.health.set(response),
  });
}

// GOOD - Simple one-time load
health = toSignal(this.http.get<HealthResponse>('/api/health'));

// GOOD - With refresh trigger using Subject
private refresh$ = new Subject<void>();
health = toSignal(
  this.refresh$.pipe(
    startWith(undefined),
    switchMap(() => this.http.get<HealthResponse>('/api/health'))
  )
);
refresh() {
  this.refresh$.next();
}
```

### Signal-Based APIs (Angular 21)

**Use signal-based functions instead of decorators:**

```typescript
// BAD - decorator-based (deprecated)
@Output() save = new EventEmitter<void>();
@ViewChild('input') inputEl!: ElementRef;
@ViewChildren('item') items!: QueryList<ElementRef>;

// GOOD - signal-based
save = output<void>();
inputEl = viewChild<ElementRef>('input');
items = viewChildren<ElementRef>('item');
```

**Signal queries return signals** - call them to get the value:

```typescript
// viewChild returns Signal<T | undefined>
// viewChildren returns Signal<readonly T[]>
const inputs = this.items();  // readonly ElementRef[]
inputs[0]?.nativeElement.focus();
```

**Use `afterNextRender` instead of `ngAfterViewInit` + setTimeout:**

```typescript
// BAD - lifecycle hook with setTimeout
ngAfterViewInit(): void {
  setTimeout(() => {
    this.inputEl.nativeElement.focus();
  }, 0);
}

// GOOD - afterNextRender in constructor
constructor() {
  afterNextRender(() => {
    this.inputEl()?.nativeElement.focus();
  });
}

// GOOD - afterNextRender after state change
addItem(): void {
  this.items.update(list => [...list, newItem]);
  afterNextRender(() => {
    const inputs = this.itemInputs();
    inputs[inputs.length - 1]?.nativeElement.focus();
  });
}
```

### Component Guidelines

- **Keep app.component minimal** - it should only contain the shell layout and router outlet
- **Feature pages go in feature folders** - e.g., `src/app/diagnostics/`
- **All components are standalone** - this is Angular 21 default, do not include `standalone: true` in decorator
- **Lazy-load routes** - use `loadComponent` in route definitions

```typescript
// app.routes.ts
export const routes: Routes = [
  { path: 'diagnostics', loadComponent: () => import('./diagnostics/diagnostics.component').then(m => m.DiagnosticsComponent) },
];
```

### Component File Structure

**Always use 3 separate files for each component:**

```
feature/
├── feature.component.ts      # Component class
├── feature.component.html    # Template
└── feature.component.scss    # Styles (can be empty, but file must exist)
```

**Component decorator pattern:**

```typescript
import { Component } from '@angular/core';

@Component({
  selector: 'app-feature',
  templateUrl: './feature.component.html',
  styleUrl: './feature.component.scss',
  imports: [/* required imports */],
})
export class FeatureComponent {
  // ...
}
```

**Do NOT use:**
- `standalone: true` - it's the Angular 21 default
- `template:` - always use `templateUrl:` with separate .html file
- `styles:` - always use `styleUrl:` with separate .scss file

### File Organization

```
src/app/
├── app.component.ts        # Minimal shell with router-outlet
├── app.component.html
├── app.component.scss
├── app.routes.ts           # Route definitions
├── app.config.ts           # App configuration
├── shared/                 # Shared components, pipes, directives
│   ├── components/
│   ├── pipes/
│   └── services/
├── diagnostics/            # Feature module
│   ├── diagnostics.component.ts
│   ├── diagnostics.component.html
│   └── diagnostics.component.scss
├── accounts/               # Feature module
│   ├── account-list.component.ts
│   ├── account-list.component.html
│   └── account-list.component.scss
└── transactions/           # Feature module
    └── ...
```

## Styling

- **Tailwind CSS only** - no component library CSS
- Use Tailwind utility classes in templates
- Use `.scss` files for component-specific styles and `:host` styling

### Global Styles (styles.css)

Common UI patterns are defined in `src/styles.css` using `@apply`. Use these classes instead of repeating Tailwind utilities:

**Cards/Panels:**
- `.card` - white background, rounded corners, subtle border and shadow

**Buttons:**
- `.btn` - base button styles (use with a variant)
- `.btn-primary` - blue primary action button
- `.btn-secondary` - white/gray secondary button
- `.btn-success` - green success/add button

**Forms:**
- Global styles automatically apply to `input`, `select`, `textarea`
- `.input-compact` - smaller padding for dense forms (apply to parent or element)
- `.label-compact` - smaller label text for dense forms

**Tables:**
- Global styles automatically apply to `table`, `thead`, `th`, `tbody`, `td`
- `.cell-primary` - darker text for primary column content
- `.row-hover` - highlight row on hover
- `.row-clickable` - hover highlight + pointer cursor

**Dialogs:**
- Global styles automatically apply to `<dialog>` elements
- `.dialog-header` - flex header with border-bottom, responsive padding
- `.dialog-header-title` - dialog title text style
- `.dialog-close-btn` - close button in header
- `.dialog-footer` - flex footer with border-top and gray background
- `.dialog-shortcuts` - hidden on mobile, shows keyboard shortcut hints
- `.dialog-actions` - flex container for action buttons

**Badges:**
- `.badge` - base badge style (use with a color variant)
- `.badge-gray` - gray badge for type labels
- `.badge-blue`, `.badge-green`, `.badge-red`, `.badge-yellow` - color variants
- `.primary-star` - yellow star indicator for primary items

**Icon Buttons:**
- `.icon-btn` - base icon button (gray, hover to darker gray)
- `.icon-btn-edit` - hover to blue
- `.icon-btn-delete` - hover to red
- `.icon-btn-move` - small text for up/down arrows with disabled state
- `.icon-btn-group` - horizontal flex container for icon buttons
- `.icon-btn-vertical` - vertical flex container (for up/down pairs)

```html
<!-- Example usage -->
<div class="card p-4">
  <div class="input-compact">
    <label class="label-compact">Date</label>
    <input type="date" />
  </div>
  <button class="btn btn-primary">Save</button>
</div>

<table>
  <tbody>
    <tr class="row-clickable">
      <td class="cell-primary">Primary content</td>
      <td>Secondary content</td>
    </tr>
  </tbody>
</table>
```

### Spacing: Prefer Gap Over Margins

**Avoid asymmetric margins** (`mb-*`, `mt-*`, `ml-*`, `mr-*`) between sibling elements. Instead, use `flex` or `flex-col` with `gap-*` on the parent container:

```html
<!-- BAD - asymmetric margins -->
<div>
  <h1 class="mb-6">Title</h1>
  <div class="card mb-6">Filter bar</div>
  <div class="card">Content</div>
</div>

<!-- GOOD - gap on parent -->
<div class="flex flex-col gap-6">
  <h1>Title</h1>
  <div class="card">Filter bar</div>
  <div class="card">Content</div>
</div>

<!-- BAD - horizontal margin -->
<div>
  <span class="font-medium">Label:</span>
  <span class="ml-2">Value</span>
</div>

<!-- GOOD - horizontal gap -->
<div class="flex gap-2">
  <span class="font-medium">Label:</span>
  <span>Value</span>
</div>
```

**Why:** Gap-based spacing is symmetric, predictable, and easier to maintain. It keeps spacing concerns on the parent rather than scattered across children.

**When margins are OK:**
- Padding inside elements (`p-*`, `px-*`, `py-*`)
- Single elements that need specific positioning
- Border-adjacent spacing like `pt-4 border-t` for visual separation

## Keyboard Navigation

This is a keyboard-first application. Every feature must be fully operable via keyboard.

### Implementation Patterns

```typescript
// Global shortcuts via host property (NOT @HostListener decorator)
@Component({
  selector: 'app-feature',
  templateUrl: './feature.component.html',
  styleUrl: './feature.component.scss',
  host: {
    '(window:keydown)': 'handleKeydown($event)',
  },
})
export class FeatureComponent {
  handleKeydown(event: KeyboardEvent): void {
    if (event.ctrlKey && event.key === 'n') {
      event.preventDefault();
      this.newTransaction();
    }
  }
}
```

**Do NOT use `@HostListener` decorator** - always use the `host` property in `@Component` instead.

### Required Shortcuts
- `Ctrl+Shift+N` - New transaction (avoid browser's Ctrl+N)
- `Ctrl+S` - Save current form
- `Escape` - Close modal/cancel
- `Arrow keys` - Navigate lists and tables
- `Enter` - Select/open item
- `Tab` - Standard focus navigation

### Avoid Browser Hotkeys
Never use these common browser shortcuts:
- `Ctrl+N` - New window
- `Ctrl+T` - New tab
- `Ctrl+W` - Close tab
- `Ctrl+L` / `Ctrl+D` - Address bar / Bookmark
- `Ctrl+H` / `Ctrl+J` - History / Downloads
- `F5` / `Ctrl+R` - Refresh

### Focus Management
- Trap focus in modals (`cdkTrapFocus`)
- Return focus to trigger element on modal close
- Auto-focus first input on form open

## Testing

- **Vitest** for unit tests
- **Playwright** for e2e tests
- Test keyboard navigation explicitly in e2e tests

```bash
# Run inside container
docker compose exec frontend pnpm test      # Vitest
docker compose exec frontend pnpm e2e       # Playwright
docker compose exec frontend pnpm lint      # ESLint
docker compose exec frontend pnpm knip      # Dead code detection
```

## TypeScript Style

- Strict TypeScript settings
- Interfaces over classes for data shapes
- camelCase for variables, PascalCase for components
- Explicit return types on public methods
