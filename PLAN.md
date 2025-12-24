# Development Plan

Check boxes as tasks complete. Claude should read this file at session start to understand current progress.

---

## Phase 1: Project Scaffolding
- [x] Create README.md
- [x] Create CLAUDE.md
- [ ] Initialize Angular 17+ frontend with standalone components
- [ ] Configure Tailwind CSS
- [ ] Install Angular CDK
- [ ] Initialize FastAPI backend
- [ ] Set up project directory structure
- [ ] Create Dockerfile (single container)
- [ ] Create docker-compose.yml for local dev with PostgreSQL
- [ ] Configure FastAPI to serve Angular static build

## Phase 2: Database Layer
- [ ] Review and document existing schema (user provides SQL)
- [ ] Set up psycopg3 async connection pool
- [ ] Create database configuration (env vars, SSL)
- [ ] Create base query execution helpers
- [ ] Write account queries
- [ ] Write transaction queries
- [ ] Write contact queries
- [ ] Write password vault queries

## Phase 3: Core API Routes
- [ ] Health check endpoint
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

**Last session:** Initial project setup - created README.md, CLAUDE.md, PLAN.md

**Next steps:** Awaiting SQL schema from user, then begin Phase 1 scaffolding

**Blockers:** None

---

## Schema Status

- [ ] Schema SQL received
- [ ] Schema reviewed and documented
- [ ] Entity relationships mapped
- [ ] Pydantic models drafted from schema
