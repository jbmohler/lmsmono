# Development Plan

Check boxes as tasks complete. Claude should read this file at session start to understand current progress.

---

## Phase 1: Project Scaffolding
- [x] Create README.md
- [x] Create CLAUDE.md
- [x] Initialize Angular 21 frontend with standalone components
- [x] Configure Tailwind CSS 4
- [x] Install Angular CDK
- [x] Initialize FastAPI backend
- [x] Set up project directory structure
- [x] Create docker-compose.yml for local dev with PostgreSQL
- [x] Configure Nginx reverse proxy for dev
- [x] Schema auto-import on database init
- [ ] Create production Dockerfile (single container)
- [ ] Configure FastAPI to serve Angular static build (production)

## Phase 2: Database Layer
- [x] Schema SQL received (6 files: core, authentication, contacts, databits, lmshacc, roscoe)
- [ ] Set up psycopg3 async connection pool
- [x] Create database configuration (Docker secrets)
- [ ] Create base query execution helpers
- [ ] Write account queries
- [ ] Write transaction queries
- [ ] Write contact queries
- [ ] Write password vault queries

## Phase 3: Core API Routes
- [x] Health check endpoint
- [ ] Accounts CRUD endpoints
- [ ] Transactions CRUD endpoints
- [ ] Contacts CRUD endpoints
- [ ] Error handling middleware
- [ ] Request/response Pydantic models

## Phase 4: Frontend Foundation
- [ ] Create app layout (header, sidebar, main content)
- [ ] Set up Angular routing with lazy loading
- [ ] Implement global keyboard shortcut service
- [ ] Create base table component with keyboard navigation
- [ ] Create base form component patterns
- [ ] Create modal/dialog service with focus trapping
- [ ] Implement responsive navigation (desktop sidebar, mobile menu)

## Phase 5: Accounts Module
- [ ] Account list view with keyboard navigation
- [ ] Account create/edit form
- [ ] Account type handling (Asset, Liability, Equity, Income, Expense)
- [ ] Account hierarchy/parent support (if in schema)
- [ ] Account balance display

## Phase 6: Transactions Module
- [ ] Transaction list view with filters
- [ ] Transaction entry form (multi-line double-entry)
- [ ] Debit/credit balance validation
- [ ] Date picker with keyboard support
- [ ] Account selection autocomplete
- [ ] Contact/payee selection
- [ ] Transaction edit and void
- [ ] Keyboard shortcuts for rapid entry

## Phase 7: Contacts Module
- [ ] Contact list view
- [ ] Contact create/edit form
- [ ] Contact search/filter
- [ ] Link contacts to transactions
- [ ] Contact detail view showing transaction history

## Phase 8: Reports
- [ ] Report date range selector
- [ ] Profit & Loss report
- [ ] Balance Sheet report
- [ ] Transaction register/journal
- [ ] Report export (CSV, PDF TBD)
- [ ] Print-friendly styling

## Phase 9: Password Vault
- [ ] Tenant/family group model integration
- [ ] Credential CRUD API with tenant isolation
- [ ] Credential list view
- [ ] Credential create/edit form
- [ ] Password visibility toggle
- [ ] Copy-to-clipboard functionality
- [ ] Sharing permissions UI
- [ ] Share/unshare credentials with family members
- [ ] Link credentials to contacts
- [ ] Security audit (tenant isolation verification)

## Phase 10: Authentication & Authorization
- [ ] Determine auth approach (session, JWT, OAuth)
- [ ] Login/logout flow
- [ ] User session management
- [ ] Route guards in Angular
- [ ] API authentication middleware
- [ ] Tenant context for password vault

## Phase 11: Polish & Production
- [ ] Mobile UI testing and fixes
- [ ] Keyboard navigation audit (all features)
- [ ] Performance optimization
- [ ] Error handling and user feedback
- [ ] Loading states
- [ ] Production Docker build optimization
- [ ] Environment configuration
- [ ] Deployment documentation

---

## Session Notes

_Use this section to leave notes for the next session._

**Last session (2026-01-17):**
- Fixed Angular build (TypeScript 5.7→5.9 for Angular 21 compatibility)
- Fixed Nginx config (dynamic DNS resolution for Docker)
- Removed exposed PostgreSQL port (now internal only)
- Created schema init script with correct load order
- Moved SQL files to `schema/sql/` subdirectory

**Next steps:** Set up psycopg3 async connection pool, create query helpers

**Blockers:** None

---

## Schema Status

- [x] Schema SQL received
- [ ] Schema reviewed and documented
- [ ] Entity relationships mapped
- [ ] Pydantic models drafted from schema

### Schema Overview
- `yenotsys` - Core system (eventlog, utility functions)
- `public` - Authentication (users, roles, sessions, activities)
- `contacts` - Contact management (personas, addresses, phones, emails, URLs)
- `databits` - Password vault (bits, tags)
- `hacc` - Accounting (accounts, accounttypes, journals, transactions, splits, tags)
