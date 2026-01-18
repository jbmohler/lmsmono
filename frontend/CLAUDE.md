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
- Extract repeated patterns to `@apply` in component styles if needed

## Keyboard Navigation

This is a keyboard-first application. Every feature must be fully operable via keyboard.

### Implementation Patterns

```typescript
// Use Angular CDK ListKeyManager for list navigation
@ViewChildren(ListItemDirective) items: QueryList<ListItemDirective>;
keyManager = new ListKeyManager(this.items).withWrap().withHomeAndEnd();

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
- `Ctrl+N` - New transaction
- `Ctrl+S` - Save current form
- `Escape` - Close modal/cancel
- `Arrow keys` - Navigate lists and tables
- `Enter` - Select/open item
- `Tab` - Standard focus navigation

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
