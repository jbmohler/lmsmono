# Contacts API Implementation Plan

This document outlines the implementation plan for the Contacts API, which serves the Angular frontend's contacts feature.

---

## Overview

The Contacts API manages **personas** (individuals or corporate entities) and their associated **contact bits** (emails, phones, addresses, URLs). The frontend expects a two-panel split view with search, keyboard navigation, and inline editing.

---

## Database Schema Reference

### Core Tables

| Table | Purpose |
|-------|---------|
| `contacts.personas` | Main contact entity (individual or corporate) |
| `contacts.email_addresses` | Email contact bits |
| `contacts.phone_numbers` | Phone contact bits |
| `contacts.street_addresses` | Street address contact bits |
| `contacts.urls` | URL/login contact bits (with encrypted passwords) |
| `contacts.persona_shares` | Sharing permissions |
| `contacts.tags` | Hierarchical tag definitions |
| `contacts.tagpersona` | Tag-to-persona assignments |

### Views

| View | Purpose |
|------|---------|
| `contacts.personas_calc` | Personas with `entity_name` and `fts_search` |
| `contacts.bits` | Unified view of all bit types with `bit_data` JSON |

---

## API Endpoints

### Personas (Core CRUD)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/contacts` | List personas with search/pagination |
| `GET` | `/api/contacts/{id}` | Get single persona with all bits |
| `POST` | `/api/contacts` | Create new persona |
| `PUT` | `/api/contacts/{id}` | Update persona fields |
| `DELETE` | `/api/contacts/{id}` | Delete persona and all bits |

### Contact Bits (Nested Resources)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/contacts/{id}/bits` | Add a contact bit |
| `PUT` | `/api/contacts/{id}/bits/{bit_id}` | Update a contact bit |
| `DELETE` | `/api/contacts/{id}/bits/{bit_id}` | Remove a contact bit |
| `POST` | `/api/contacts/{id}/bits/reorder` | Bulk update bit sequences |

### Tags (Future Enhancement)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/contacts/tags` | List all tags |
| `POST` | `/api/contacts/{id}/tags` | Assign tag to persona |
| `DELETE` | `/api/contacts/{id}/tags/{tag_id}` | Remove tag from persona |

---

## Request/Response DTOs

### Persona DTOs

```python
@dataclass
class PersonaCreate:
    """Create a new persona."""
    is_corporate: bool
    last_name: str                    # Required: company name or surname
    first_name: str | None = None     # Individual only
    title: str | None = None          # Individual only (Mr., Dr., etc.)
    organization: str | None = None   # Individual's org affiliation
    memo: str | None = None
    birthday: date | None = None
    anniversary: date | None = None


@dataclass
class PersonaUpdate:
    """Partial update for persona fields."""
    is_corporate: bool | None = None
    last_name: str | None = None
    first_name: str | None = None
    title: str | None = None
    organization: str | None = None
    memo: str | None = None
    birthday: date | None = None
    anniversary: date | None = None
```

### Contact Bit DTOs

```python
@dataclass
class BitCreate:
    """Create a new contact bit."""
    bit_type: Literal["email", "phone", "address", "url"]
    name: str | None = None           # Label (Work, Home, etc.)
    memo: str | None = None
    is_primary: bool = False
    bit_sequence: int = 0

    # Type-specific fields (validated based on bit_type)
    email: str | None = None          # email type
    number: str | None = None         # phone type
    address1: str | None = None       # address type
    address2: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    url: str | None = None            # url type
    username: str | None = None


@dataclass
class BitUpdate:
    """Partial update for contact bit."""
    name: str | None = None
    memo: str | None = None
    is_primary: bool | None = None
    bit_sequence: int | None = None

    # Type-specific (only relevant fields apply)
    email: str | None = None
    number: str | None = None
    address1: str | None = None
    address2: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    url: str | None = None
    username: str | None = None


@dataclass
class BitReorderItem:
    """Single item in reorder request."""
    id: UUID
    bit_sequence: int


@dataclass
class BitReorderRequest:
    """Bulk reorder contact bits."""
    items: list[BitReorderItem]
```

---

## Column Definitions

### Persona List Columns

```python
PERSONA_LIST_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="entity_name", label="Name", type="string"),
    ColumnMeta(key="is_corporate", label="Corporate", type="boolean"),
    ColumnMeta(key="organization", label="Organization", type="string"),
    ColumnMeta(key="primary_email", label="Email", type="string"),
    ColumnMeta(key="primary_phone", label="Phone", type="string"),
]
```

### Persona Detail Columns

```python
PERSONA_DETAIL_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="is_corporate", label="Corporate", type="boolean"),
    ColumnMeta(key="last_name", label="Last Name", type="string"),
    ColumnMeta(key="first_name", label="First Name", type="string"),
    ColumnMeta(key="title", label="Title", type="string"),
    ColumnMeta(key="organization", label="Organization", type="string"),
    ColumnMeta(key="memo", label="Memo", type="string"),
    ColumnMeta(key="birthday", label="Birthday", type="date"),
    ColumnMeta(key="anniversary", label="Anniversary", type="date"),
    ColumnMeta(key="bits", label="Contact Info", type="array"),
]
```

### Contact Bit Columns

```python
BIT_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="bit_type", label="Type", type="string"),
    ColumnMeta(key="name", label="Label", type="string"),
    ColumnMeta(key="memo", label="Memo", type="string"),
    ColumnMeta(key="is_primary", label="Primary", type="boolean"),
    ColumnMeta(key="bit_sequence", label="Order", type="number"),
    ColumnMeta(key="bit_data", label="Data", type="object"),
]
```

---

## SQL Queries

### List Personas with Search

```sql
-- queries/contacts/list_personas.sql
SELECT
    p.id,
    p.corporate_entity AS is_corporate,
    p.l_name AS last_name,
    p.f_name AS first_name,
    p.title,
    p.organization,
    p.memo,
    p.birthday,
    p.anniversary,
    pc.entity_name,
    (
        SELECT email
        FROM contacts.email_addresses
        WHERE persona_id = p.id AND is_primary = true
        LIMIT 1
    ) AS primary_email,
    (
        SELECT number
        FROM contacts.phone_numbers
        WHERE persona_id = p.id AND is_primary = true
        LIMIT 1
    ) AS primary_phone
FROM contacts.personas p
JOIN contacts.personas_calc pc ON pc.id = p.id
WHERE
    p.owner_id = %(owner_id)s
    AND (
        %(search)s IS NULL
        OR pc.fts_search @@ websearch_to_tsquery('english', %(search)s)
    )
ORDER BY pc.entity_name
LIMIT %(limit)s OFFSET %(offset)s
```

### Get Persona with Bits

```sql
-- queries/contacts/get_persona.sql
SELECT
    p.id,
    p.corporate_entity AS is_corporate,
    p.l_name AS last_name,
    p.f_name AS first_name,
    p.title,
    p.organization,
    p.memo,
    p.birthday,
    p.anniversary,
    pc.entity_name
FROM contacts.personas p
JOIN contacts.personas_calc pc ON pc.id = p.id
WHERE p.id = %(id)s AND p.owner_id = %(owner_id)s
```

### Get Contact Bits for Persona

```sql
-- queries/contacts/get_bits.sql
SELECT
    id,
    bit_type,
    name,
    memo,
    is_primary,
    bit_sequence,
    bit_data
FROM contacts.bits
WHERE persona_id = %(persona_id)s
ORDER BY bit_type, bit_sequence, name
```

### Insert Persona

```sql
-- queries/contacts/insert_persona.sql
INSERT INTO contacts.personas (
    id, owner_id, corporate_entity, l_name, f_name,
    title, organization, memo, birthday, anniversary
)
VALUES (
    gen_random_uuid(), %(owner_id)s, %(is_corporate)s, %(last_name)s, %(first_name)s,
    %(title)s, %(organization)s, %(memo)s, %(birthday)s, %(anniversary)s
)
RETURNING id
```

### Insert Contact Bit (Email Example)

```sql
-- queries/contacts/insert_email.sql
INSERT INTO contacts.email_addresses (
    id, persona_id, email, name, memo, is_primary, bit_sequence
)
VALUES (
    gen_random_uuid(), %(persona_id)s, %(email)s, %(name)s,
    %(memo)s, %(is_primary)s, %(bit_sequence)s
)
RETURNING id
```

### Update Persona (Dynamic)

```python
# Dynamic query building for partial updates
updates = []
params = {"id": persona_id, "owner_id": owner_id}

if data.last_name is not None:
    updates.append("l_name = %(last_name)s")
    params["last_name"] = data.last_name
# ... more fields

query = f"""
    UPDATE contacts.personas
    SET {', '.join(updates)}
    WHERE id = %(id)s AND owner_id = %(owner_id)s
    RETURNING id
"""
```

### Delete Persona (Cascade via FK)

```sql
-- Foreign keys have ON DELETE CASCADE, so bits are auto-deleted
DELETE FROM contacts.personas
WHERE id = %(id)s AND owner_id = %(owner_id)s
```

---

## Response Formats

### GET /api/contacts (List)

```json
{
  "columns": [
    {"key": "id", "label": "ID", "type": "uuid"},
    {"key": "entity_name", "label": "Name", "type": "string"},
    {"key": "is_corporate", "label": "Corporate", "type": "boolean"},
    {"key": "organization", "label": "Organization", "type": "string"},
    {"key": "primary_email", "label": "Email", "type": "string"},
    {"key": "primary_phone", "label": "Phone", "type": "string"}
  ],
  "data": [
    {
      "id": "a1b2c3d4-...",
      "entity_name": "John Smith",
      "is_corporate": false,
      "organization": "Acme Corp",
      "primary_email": "john@acme.com",
      "primary_phone": "555-1234"
    }
  ]
}
```

### GET /api/contacts/{id} (Detail)

```json
{
  "columns": [...],
  "data": {
    "id": "a1b2c3d4-...",
    "is_corporate": false,
    "last_name": "Smith",
    "first_name": "John",
    "title": "Mr.",
    "organization": "Acme Corp",
    "memo": "Key contact",
    "birthday": "1985-03-15",
    "anniversary": null,
    "entity_name": "Mr. John Smith",
    "bits": [
      {
        "id": "bit-uuid-1",
        "bit_type": "email",
        "name": "Work",
        "memo": null,
        "is_primary": true,
        "bit_sequence": 0,
        "bit_data": {"email": "john@acme.com"}
      },
      {
        "id": "bit-uuid-2",
        "bit_type": "phone",
        "name": "Mobile",
        "memo": null,
        "is_primary": true,
        "bit_sequence": 0,
        "bit_data": {"number": "555-1234"}
      }
    ]
  }
}
```

---

## Frontend Field Mapping

The API uses snake_case; the frontend uses camelCase. Mapping:

| API Field | Frontend Field |
|-----------|----------------|
| `is_corporate` | `isCorporate` |
| `last_name` | `lastName` |
| `first_name` | `firstName` |
| `entity_name` | `entityName` |
| `bit_type` | `bitType` |
| `bit_sequence` | `bitSequence` |
| `is_primary` | `isPrimary` |
| `bit_data` | Flattened into bit object |

The frontend service should transform responses to match its model interfaces.

---

## Seed Data

### Sample Personas

```python
SEED_PERSONAS = [
    # Individual contacts
    {
        "is_corporate": False,
        "first_name": "Alice",
        "last_name": "Johnson",
        "title": "Ms.",
        "organization": "TechStart Inc",
        "memo": "Primary vendor contact",
        "birthday": "1988-06-12",
    },
    {
        "is_corporate": False,
        "first_name": "Bob",
        "last_name": "Williams",
        "title": "Mr.",
        "organization": "Consulting Group LLC",
        "memo": None,
        "birthday": None,
    },
    {
        "is_corporate": False,
        "first_name": "Carol",
        "last_name": "Martinez",
        "title": "Dr.",
        "organization": None,
        "memo": "Family physician",
        "birthday": "1975-02-28",
    },

    # Corporate contacts
    {
        "is_corporate": True,
        "first_name": None,
        "last_name": "Acme Corporation",
        "title": None,
        "organization": None,
        "memo": "Main supplier",
    },
    {
        "is_corporate": True,
        "first_name": None,
        "last_name": "City Electric Utility",
        "title": None,
        "organization": None,
        "memo": "Monthly utility bill",
    },
]
```

### Sample Bits per Persona

```python
# For Alice Johnson
ALICE_BITS = [
    {"bit_type": "email", "email": "alice.johnson@techstart.io", "name": "Work", "is_primary": True, "bit_sequence": 0},
    {"bit_type": "email", "email": "alice.j@gmail.com", "name": "Personal", "is_primary": False, "bit_sequence": 1},
    {"bit_type": "phone", "number": "555-0101", "name": "Office", "is_primary": True, "bit_sequence": 0},
    {"bit_type": "phone", "number": "555-0102", "name": "Mobile", "is_primary": False, "bit_sequence": 1},
    {"bit_type": "address", "address1": "123 Tech Park Dr", "address2": "Suite 400", "city": "San Jose", "state": "CA", "zip": "95110", "country": "USA", "name": "Office", "is_primary": True, "bit_sequence": 0},
]

# For Acme Corporation
ACME_BITS = [
    {"bit_type": "phone", "number": "800-555-ACME", "name": "Main", "is_primary": True, "bit_sequence": 0},
    {"bit_type": "phone", "number": "800-555-2264", "name": "Support", "is_primary": False, "bit_sequence": 1},
    {"bit_type": "email", "email": "orders@acme.com", "name": "Orders", "is_primary": True, "bit_sequence": 0},
    {"bit_type": "email", "email": "support@acme.com", "name": "Support", "is_primary": False, "bit_sequence": 1},
    {"bit_type": "url", "url": "https://acme.com", "username": None, "name": "Website", "is_primary": True, "bit_sequence": 0},
    {"bit_type": "url", "url": "https://portal.acme.com", "username": "customer123", "name": "Portal", "is_primary": False, "bit_sequence": 1},
    {"bit_type": "address", "address1": "1 Industrial Way", "city": "Commerce", "state": "CA", "zip": "90040", "country": "USA", "name": "HQ", "is_primary": True, "bit_sequence": 0},
]
```

---

## Implementation Order

### Phase 1: Core Personas API ✓
- [x] Create `backend/api/contacts.py` with `ContactsController`
- [x] Implement `GET /api/contacts` (list with search)
- [x] Implement `GET /api/contacts/{id}` (detail with bits)
- [x] Implement `POST /api/contacts` (create persona)
- [x] Implement `PUT /api/contacts/{id}` (update persona)
- [x] Implement `DELETE /api/contacts/{id}` (delete persona)
- [x] Register controller in `app.py`

### Phase 2: Contact Bits API ✓
- [x] Implement `POST /api/contacts/{id}/bits` (add bit)
- [x] Implement `PUT /api/contacts/{id}/bits/{bit_id}` (update bit)
- [x] Implement `DELETE /api/contacts/{id}/bits/{bit_id}` (remove bit)
- [x] Implement `POST /api/contacts/{id}/bits/reorder` (bulk reorder)

### Phase 3: Seed Data ✓
- [x] Create `backend/seed/users.py` (dev user for FK constraint)
- [x] Create `backend/seed/contacts.py` (personas and bits)
- [x] Create `backend/seed/run.py` (CLI entry point)

### Phase 4: Frontend Integration ✓
- [x] Create `ContactsService` with HTTP calls
- [x] Update `ContactsComponent` to use real data
- [x] Add case transformation (snake_case ↔ camelCase)
- [x] Handle loading and error states

### Phase 5: Bit Edit Dialog with Password Support

A focused dialog for editing individual contact bits with full support for all field types, including secure password handling for URL bits.

#### Backend Changes

**5.1 Extend URL bit fields in API**

Add password-related date fields to the bit response and update DTOs:

```python
# URL bit response includes (password_enc never exposed directly):
{
  "id": "...",
  "bit_type": "url",
  "name": "Portal",
  "url": "https://portal.example.com",
  "username": "user123",
  "has_password": true,           # Boolean flag (password_enc IS NOT NULL)
  "pw_reset_dt": "2025-01-15",    # Date password was last changed
  "pw_next_reset_dt": "2025-04-15" # Date password should be changed
}
```

Update `BitCreate` and `BitUpdate` DTOs:
```python
@dataclass
class BitCreate:
    # ... existing fields ...
    password: str | None = None           # Plaintext, encrypted before storage
    pw_reset_dt: date | None = None
    pw_next_reset_dt: date | None = None

@dataclass
class BitUpdate:
    # ... existing fields ...
    password: str | None = None           # If provided, re-encrypt and update
    clear_password: bool = False          # If true, set password_enc to NULL
    pw_reset_dt: date | None = None
    pw_next_reset_dt: date | None = None
```

**5.2 Secure password retrieval endpoint**

Add a dedicated endpoint for decrypting passwords (logged, rate-limited in production):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/contacts/{id}/bits/{bit_id}/password` | Decrypt and return password |

Response:
```json
{
  "password": "the-decrypted-password"
}
```

Security considerations:
- Only URL bits have passwords
- Returns 404 if bit has no password
- Should be audit-logged in production
- Consider rate limiting

**5.3 Update `contacts.bits` view handling**

Modify `_get_bits_for_persona()` to include:
- `has_password` (boolean): `password_enc IS NOT NULL`
- `pw_reset_dt` (date): Last password change
- `pw_next_reset_dt` (date): Next required change

#### Frontend Changes

**5.4 Create `BitEditDialogComponent`**

New standalone dialog component for editing a single bit:

```
frontend/src/app/contacts/
├── bit-edit-dialog/
│   ├── bit-edit-dialog.component.ts
│   ├── bit-edit-dialog.component.html
│   └── bit-edit-dialog.component.scss
```

Features:
- Opens as a modal dialog (uses `<dialog>` element)
- Receives bit data as input
- Emits saved bit or cancel
- Type-specific form fields based on `bitType`

**5.5 Type-specific form layouts**

**Email bit:**
```
┌─────────────────────────────────────────┐
│ Edit Email                          [×] │
├─────────────────────────────────────────┤
│ Label:    [Work________________]        │
│ Email:    [john@example.com____]        │
│ Primary:  [✓]                           │
│ Memo:     [Notes about this email]      │
├─────────────────────────────────────────┤
│                    [Cancel]  [Save]     │
└─────────────────────────────────────────┘
```

**Phone bit:**
```
┌─────────────────────────────────────────┐
│ Edit Phone                          [×] │
├─────────────────────────────────────────┤
│ Label:    [Mobile______________]        │
│ Number:   [(555) 123-4567______]        │
│ Primary:  [✓]                           │
│ Memo:     [Best time: afternoons]       │
├─────────────────────────────────────────┤
│                    [Cancel]  [Save]     │
└─────────────────────────────────────────┘
```

**Address bit:**
```
┌─────────────────────────────────────────┐
│ Edit Address                        [×] │
├─────────────────────────────────────────┤
│ Label:    [Office______________]        │
│ Address:  [123 Main Street_____]        │
│           [Suite 400___________]        │
│ City:     [Springfield_________]        │
│ State:    [IL__] ZIP: [62701___]        │
│ Country:  [USA_________________]        │
│ Primary:  [✓]                           │
│ Memo:     [Use back entrance___]        │
├─────────────────────────────────────────┤
│                    [Cancel]  [Save]     │
└─────────────────────────────────────────┘
```

**URL bit (with password vault features):**
```
┌─────────────────────────────────────────┐
│ Edit Link                           [×] │
├─────────────────────────────────────────┤
│ Label:    [Customer Portal_____]        │
│ URL:      [https://portal.acme.com]     │
│ Username: [customer123_________]        │
│                                         │
│ ┌─ Password ──────────────────────────┐ │
│ │ [••••••••••••] [👁] [📋]            │ │
│ │ [Change Password...]                │ │
│ │                                     │ │
│ │ Last changed:  2025-01-15           │ │
│ │ Change by:     2025-04-15 (90 days) │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Primary:  [✓]                           │
│ Memo:     [Use SSO when possible]       │
├─────────────────────────────────────────┤
│                    [Cancel]  [Save]     │
└─────────────────────────────────────────┘
```

**5.6 Password field features**

- **Masked display**: Show `••••••••` by default
- **Show/hide toggle**: Eye icon to reveal password temporarily
- **Copy to clipboard**: Button to copy password without revealing
  - Uses Clipboard API: `navigator.clipboard.writeText(password)`
  - Shows brief "Copied!" confirmation
- **Change password**: Expands to show new password input fields
- **Password dates**: Display and edit reset dates
- **Visual warnings**: Highlight if password is overdue for change

**5.7 Update `ContactsService`**

Add method to fetch decrypted password:

```typescript
async getPassword(contactId: string, bitId: string): Promise<string> {
  const response = await this.api
    .getOne<{ password: string }>(`/api/contacts/${contactId}/bits/${bitId}/password`)
    .toPromise();
  return response!.data.password;
}
```

**5.8 Update `ContactDetailComponent`**

- Add click handler to open dialog for each bit
- Replace inline edit mode with dialog-based editing
- Keep inline display in view mode
- Handle dialog save/cancel events

**5.9 Keyboard shortcuts**

- `Enter` on a bit row: Open edit dialog
- `Escape`: Close dialog without saving
- `Ctrl+S`: Save and close dialog
- Focus trap within dialog

#### Updated Frontend Model

Extend `ContactUrl` interface in `contacts.model.ts`:

```typescript
export interface ContactUrl extends ContactBitBase {
  bitType: 'url';
  url: string;
  username: string;
  hasPassword: boolean;        // True if password_enc is set
  passwordResetDate: string | null;    // ISO date of last change
  passwordNextResetDate: string | null; // ISO date for next change
}
```

Note: The actual password is never included in the model. It's fetched on-demand via `getPassword()` and only held in component state temporarily for clipboard operations.

#### Implementation Checklist

**Backend:**
- [x] Add `has_password`, `pw_reset_dt`, `pw_next_reset_dt` to bit response
- [x] Update `BitCreate` DTO with password date fields
- [x] Update `BitUpdate` DTO with `clear_password` flag and date fields
- [x] Update `_insert_bit()` to handle password dates
- [x] Update `_update_bit()` to handle password dates and clearing
- [x] Add `GET /api/contacts/{id}/bits/{bit_id}/password` endpoint
- [x] Update seed data with sample passwords and dates

**Frontend:**
- [ ] Create `BitEditDialogComponent` with `<dialog>` element
- [ ] Implement email bit form
- [ ] Implement phone bit form
- [ ] Implement address bit form
- [ ] Implement URL bit form with password section
- [ ] Add password show/hide toggle
- [ ] Add copy password to clipboard
- [ ] Add password change UI with date fields
- [ ] Update `ContactsService` with `getPassword()` method
- [ ] Update `ContactDetailComponent` to use dialog
- [ ] Add keyboard navigation and shortcuts
- [ ] Style with Tailwind CSS

### Phase 6: Testing
- [ ] Unit tests for API endpoints
- [ ] Unit tests for password encryption/decryption
- [ ] E2E tests for keyboard navigation
- [ ] E2E tests for bit edit dialog
- [ ] Test password copy to clipboard
- [ ] Test search with full-text search

---

## Security Considerations

1. **Owner Validation**: All queries must filter by `owner_id` from session
2. **Password Encryption**: URL passwords encrypted with Fernet (see below)
3. **Sharing**: Check `persona_shares` for non-owned contacts (future)
4. **Input Validation**: Validate bit_type matches provided fields
5. **SQL Injection**: Use parameterized queries exclusively

### Password Encryption (Fernet)

URL bit passwords are encrypted at rest using `cryptography.fernet.Fernet`:

```python
# core/crypto.py
from cryptography.fernet import Fernet

# Key loaded from config (32 bytes, base64-encoded)
_fernet: Fernet | None = None

def init_crypto(key: str) -> None:
    global _fernet
    _fernet = Fernet(key.encode())

def encrypt_password(plaintext: str) -> bytes:
    """Encrypt password for storage."""
    if not _fernet:
        raise RuntimeError("Crypto not initialized")
    return _fernet.encrypt(plaintext.encode())

def decrypt_password(ciphertext: bytes) -> str:
    """Decrypt password from storage."""
    if not _fernet:
        raise RuntimeError("Crypto not initialized")
    return _fernet.decrypt(ciphertext).decode()
```

**Key Management:**
- Fernet key stored in `secrets/config.json` as `encryption_key`
- Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Key must be 32 bytes, URL-safe base64-encoded

---

## Error Handling

| Status | Condition |
|--------|-----------|
| 400 | Invalid bit_type or mismatched fields |
| 401 | No session / authentication required |
| 403 | Contact not owned by user |
| 404 | Persona or bit not found |
| 409 | Constraint violation (e.g., duplicate) |

---

## Notes

- The `contacts.bits` view provides a unified interface for reading all bit types
- Writing bits requires inserting into type-specific tables
- Full-text search uses PostgreSQL `websearch_to_tsquery` for natural language queries
- Bit reordering swaps `bit_sequence` values; the frontend manages sequence numbers
