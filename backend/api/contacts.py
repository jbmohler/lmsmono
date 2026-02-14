from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

import psycopg
import psycopg.rows
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException, PermissionDeniedException
from litestar.params import Parameter

import core.crypto as crypto
from core.auth import AuthenticatedUser
from core.guards import require_capability
import core.db as db
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------


def sql_select_personas(filter_search: bool = False) -> str:
    """List all contacts accessible to the current user."""
    search_condition = """
        AND (
            %(search)s::text IS NULL
            OR pc.fts_search @@ websearch_to_tsquery('english', %(search)s)
        )
    """ if filter_search else ""

    return f"""
        SELECT
            p.id,
            pc.entity_name,
            p.corporate_entity AS is_corporate,
            p.organization,
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
            ) AS primary_phone,
            p.owner_id = %(user_id)s AS is_owner
        FROM contacts.personas p
        JOIN contacts.personas_calc pc ON pc.id = p.id
        JOIN contacts.persona_shares ps ON ps.persona_id = p.id
        WHERE
            ps.user_id = %(user_id)s
            {search_condition}
        ORDER BY pc.entity_name
        LIMIT %(limit)s OFFSET %(offset)s
    """


def sql_select_persona_by_id() -> str:
    """Get a single persona with calculated fields (access controlled)."""
    return """
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
            p.owner_id,
            p.owner_id = %(user_id)s AS is_owner
        FROM contacts.personas p
        JOIN contacts.personas_calc pc ON pc.id = p.id
        JOIN contacts.persona_shares ps ON ps.persona_id = p.id
        WHERE p.id = %(id)s AND ps.user_id = %(user_id)s
    """


def sql_select_persona_bits() -> str:
    """Fetch all contact bits for a persona."""
    return """
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
    """


def sql_select_persona_access() -> str:
    """Check if user can access persona (returns is_owner flag)."""
    return """
        SELECT
            p.owner_id = %(user_id)s AS is_owner
        FROM contacts.personas p
        JOIN contacts.persona_shares ps ON ps.persona_id = p.id
        WHERE p.id = %(id)s AND ps.user_id = %(user_id)s
    """


def sql_select_persona_shares() -> str:
    """Get list of users who have access to a persona."""
    return """
        SELECT
            u.id AS user_id,
            u.username,
            u.full_name,
            p.owner_id = u.id AS is_owner
        FROM contacts.persona_shares ps
        JOIN users u ON u.id = ps.user_id
        JOIN contacts.personas p ON p.id = ps.persona_id
        WHERE ps.persona_id = %(persona_id)s
        ORDER BY
            p.owner_id = u.id DESC,
            u.full_name,
            u.username
    """


def sql_select_bit_from_table(table: str) -> str:
    """Check if a bit exists in a specific table."""
    return f"SELECT id FROM {table} WHERE id = %(id)s"


def sql_select_bit_persona_id(table: str) -> str:
    """Get persona_id for a bit in a specific table."""
    return f"SELECT persona_id FROM {table} WHERE id = %(id)s"


def sql_select_bit_by_id() -> str:
    """Get a single bit from the unified view."""
    return """
        SELECT
            id,
            bit_type,
            name,
            memo,
            is_primary,
            bit_sequence,
            bit_data
        FROM contacts.bits
        WHERE id = %(bit_id)s AND persona_id = %(persona_id)s
    """


def sql_select_url_password() -> str:
    """Get encrypted password for a URL bit."""
    return """
        SELECT password_enc
        FROM contacts.urls
        WHERE id = %(bit_id)s AND persona_id = %(persona_id)s
    """


def sql_select_user_exists_active() -> str:
    """Check if a user exists and is active."""
    return "SELECT id FROM users WHERE id = %(user_id)s AND NOT inactive"


def sql_select_persona_owner() -> str:
    """Get owner_id for a persona."""
    return "SELECT owner_id FROM contacts.personas WHERE id = %(id)s"


def sql_insert_persona() -> str:
    """Create a new persona."""
    return """
        INSERT INTO contacts.personas (
            corporate_entity, l_name, f_name, title,
            organization, memo, birthday, anniversary, owner_id
        )
        VALUES (
            %(is_corporate)s, %(last_name)s, %(first_name)s, %(title)s,
            %(organization)s, %(memo)s, %(birthday)s, %(anniversary)s,
            %(owner_id)s
        )
        RETURNING id
    """


def sql_insert_persona_share() -> str:
    """Add a share for a persona (idempotent)."""
    return """
        INSERT INTO contacts.persona_shares (persona_id, user_id)
        VALUES (%(persona_id)s, %(user_id)s)
        ON CONFLICT (persona_id, user_id) DO NOTHING
    """


def sql_insert_email() -> str:
    """Insert an email address bit."""
    return """
        INSERT INTO contacts.email_addresses
            (persona_id, email, name, memo, is_primary, bit_sequence)
        VALUES
            (%(persona_id)s, %(email)s, %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
        RETURNING id
    """


def sql_insert_phone() -> str:
    """Insert a phone number bit."""
    return """
        INSERT INTO contacts.phone_numbers
            (persona_id, number, name, memo, is_primary, bit_sequence)
        VALUES
            (%(persona_id)s, %(number)s, %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
        RETURNING id
    """


def sql_insert_address() -> str:
    """Insert a street address bit."""
    return """
        INSERT INTO contacts.street_addresses
            (persona_id, address1, address2, city, state, zip, country,
             name, memo, is_primary, bit_sequence)
        VALUES
            (%(persona_id)s, %(address1)s, %(address2)s, %(city)s, %(state)s,
             %(zip)s, %(country)s, %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
        RETURNING id
    """


def sql_insert_url() -> str:
    """Insert a URL bit."""
    return """
        INSERT INTO contacts.urls
            (persona_id, url, username, password_enc, pw_reset_dt, pw_next_reset_dt,
             name, memo, is_primary, bit_sequence)
        VALUES
            (%(persona_id)s, %(url)s, %(username)s, %(password_enc)s,
             %(pw_reset_dt)s, %(pw_next_reset_dt)s,
             %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
        RETURNING id
    """


def sql_update_persona(fields: set[str]) -> str:
    """Update persona fields dynamically."""
    field_map = {
        "is_corporate": "corporate_entity",
        "last_name": "l_name",
        "first_name": "f_name",
        "title": "title",
        "organization": "organization",
        "memo": "memo",
        "birthday": "birthday",
        "anniversary": "anniversary",
    }
    updates = [f"{field_map[f]} = %({f})s" for f in fields if f in field_map]
    if not updates:
        raise ValueError("No valid fields to update")
    return f"""
        UPDATE contacts.personas
        SET {", ".join(updates)}
        WHERE id = %(id)s
    """


def sql_update_persona_owner() -> str:
    """Transfer ownership of a persona."""
    return "UPDATE contacts.personas SET owner_id = %(new_owner_id)s WHERE id = %(id)s"


def sql_update_bit(table: str, updates: list[str]) -> str:
    """Update bit fields dynamically."""
    return f"UPDATE {table} SET {', '.join(updates)} WHERE id = %(id)s"


def sql_update_bit_sequence(table: str) -> str:
    """Update bit sequence for reordering."""
    return f"""
        UPDATE {table}
        SET bit_sequence = %(bit_sequence)s
        WHERE id = %(id)s AND persona_id = %(persona_id)s
    """


def sql_delete_persona_shares() -> str:
    """Delete all shares for a persona."""
    return "DELETE FROM contacts.persona_shares WHERE persona_id = %(id)s"


def sql_delete_email_addresses() -> str:
    """Delete all email addresses for a persona."""
    return "DELETE FROM contacts.email_addresses WHERE persona_id = %(id)s"


def sql_delete_phone_numbers() -> str:
    """Delete all phone numbers for a persona."""
    return "DELETE FROM contacts.phone_numbers WHERE persona_id = %(id)s"


def sql_delete_street_addresses() -> str:
    """Delete all street addresses for a persona."""
    return "DELETE FROM contacts.street_addresses WHERE persona_id = %(id)s"


def sql_delete_urls() -> str:
    """Delete all URLs for a persona."""
    return "DELETE FROM contacts.urls WHERE persona_id = %(id)s"


def sql_delete_persona() -> str:
    """Delete a persona."""
    return "DELETE FROM contacts.personas WHERE id = %(id)s"


def sql_delete_persona_share() -> str:
    """Remove a specific share."""
    return """
        DELETE FROM contacts.persona_shares
        WHERE persona_id = %(persona_id)s AND user_id = %(user_id)s
    """


def sql_delete_bit(table: str) -> str:
    """Delete a bit from a specific table."""
    return f"DELETE FROM {table} WHERE id = %(id)s AND persona_id = %(persona_id)s"


# Valid bit types
BitType = Literal["email", "phone", "address", "url"]
BIT_TYPES: set[str] = {"email", "phone", "address", "url"}

# Map bit_type to database table name
BIT_TYPE_TABLES = {
    "email": "contacts.email_addresses",
    "phone": "contacts.phone_numbers",
    "address": "contacts.street_addresses",
    "url": "contacts.urls",
}

# Map view bit_type values to API bit_type values
VIEW_BIT_TYPE_MAP = {
    "email_addresses": "email",
    "phone_numbers": "phone",
    "street_addresses": "address",
    "urls": "url",
}


# Column definitions for persona list (summary view)
PERSONA_LIST_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="entity_name", label="Name", type="string"),
    ColumnMeta(key="is_corporate", label="Corporate", type="boolean"),
    ColumnMeta(key="organization", label="Organization", type="string"),
    ColumnMeta(key="primary_email", label="Email", type="string"),
    ColumnMeta(key="primary_phone", label="Phone", type="string"),
    ColumnMeta(key="is_owner", label="Owner", type="boolean"),
]

# Column definitions for persona detail (full view with bits)
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
    ColumnMeta(key="entity_name", label="Display Name", type="string"),
    ColumnMeta(key="bits", label="Contact Info", type="array"),
    ColumnMeta(key="owner_id", label="Owner ID", type="uuid"),
    ColumnMeta(key="is_owner", label="Owner", type="boolean"),
]


@dataclass
class PersonaCreate:
    """Create a new persona (individual or corporate contact)."""

    is_corporate: bool
    last_name: str
    first_name: str | None = None
    title: str | None = None
    organization: str | None = None
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


@dataclass
class BitCreate:
    """Create a new contact bit."""

    bit_type: str  # email, phone, address, url
    name: str | None = None  # Label (Work, Home, etc.)
    memo: str | None = None
    is_primary: bool = False
    bit_sequence: int = 0

    # Type-specific fields
    email: str | None = None  # email type
    number: str | None = None  # phone type
    address1: str | None = None  # address type
    address2: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    url: str | None = None  # url type
    username: str | None = None
    password: str | None = None  # Will be encrypted before storage
    pw_reset_dt: date | None = None  # Date password was last changed
    pw_next_reset_dt: date | None = None  # Date password should be changed


@dataclass
class BitUpdate:
    """Partial update for contact bit."""

    name: str | None = None
    memo: str | None = None
    is_primary: bool | None = None
    bit_sequence: int | None = None

    # Type-specific fields
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
    password: str | None = None  # Will be encrypted before storage
    clear_password: bool = False  # If true, set password_enc to NULL
    pw_reset_dt: date | None = None  # Date password was last changed
    pw_next_reset_dt: date | None = None  # Date password should be changed


@dataclass
class BitReorderItem:
    """Single item in reorder request."""

    id: str  # UUID as string
    bit_sequence: int


@dataclass
class BitReorderRequest:
    """Bulk reorder contact bits."""

    items: list[BitReorderItem]


async def _get_bits_for_persona(
    conn: psycopg.AsyncConnection, persona_id: UUID
) -> list[dict]:
    """Fetch all contact bits for a persona."""
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            sql_select_persona_bits(),
            {"persona_id": persona_id},
        )
        rows = await cur.fetchall()
        bits = []
        for row in rows:
            # Normalize bit_type from view format to API format
            view_bit_type = row["bit_type"]
            api_bit_type = VIEW_BIT_TYPE_MAP.get(view_bit_type, view_bit_type)

            bit: dict = {
                "id": row["id"],
                "bit_type": api_bit_type,
                "name": row["name"],
                "memo": row["memo"],
                "is_primary": row["is_primary"],
                "bit_sequence": row["bit_sequence"],
            }
            # Merge bit_data fields into the bit object
            if row["bit_data"]:
                bit_data = dict(row["bit_data"])

                # For URL bits: extract password info but never expose password_enc
                if api_bit_type == "url":
                    password_enc = bit_data.pop("password_enc", None)
                    bit["has_password"] = password_enc is not None
                    # Keep pw_reset_dt and pw_next_reset_dt as-is (they're already in bit_data)

                bit.update(bit_data)
            bits.append(bit)
        return bits


async def _get_persona_by_id(
    conn: psycopg.AsyncConnection, persona_id: UUID, user_id: str
) -> SingleRowResponse:
    """Get a single persona with all its bits.

    The user must have access via persona_shares.
    """
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            sql_select_persona_by_id(),
            {"id": persona_id, "user_id": user_id},
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")

        data = dict(row)
        data["bits"] = await _get_bits_for_persona(conn, persona_id)

        return SingleRowResponse(columns=PERSONA_DETAIL_COLUMNS, data=data)


async def _verify_persona_access(
    conn: psycopg.AsyncConnection, persona_id: UUID, user_id: str, require_owner: bool = False
) -> bool:
    """Check if user can access persona.

    Args:
        conn: Database connection
        persona_id: The persona UUID
        user_id: The user UUID
        require_owner: If True, raise 403 if user is not owner

    Returns:
        True if user is the owner, False if just shared

    Raises:
        HTTPException 404 if no access
        PermissionDeniedException if require_owner and not owner
    """
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            sql_select_persona_access(),
            {"id": persona_id, "user_id": user_id},
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")

        is_owner = row["is_owner"]
        if require_owner and not is_owner:
            raise PermissionDeniedException(detail="Only the owner can modify this contact")
        return is_owner


async def _get_bit_type(conn: psycopg.AsyncConnection, bit_id: UUID) -> str | None:
    """Determine which table a bit belongs to by checking all bit tables."""
    async with conn.cursor() as cur:
        for bit_type, table in BIT_TYPE_TABLES.items():
            await cur.execute(
                sql_select_bit_from_table(table),
                {"id": bit_id},
            )
            if await cur.fetchone():
                return bit_type
    return None


async def _insert_bit(
    conn: psycopg.AsyncConnection,
    persona_id: UUID,
    data: BitCreate,
) -> UUID:
    """Insert a new contact bit into the appropriate table."""
    if data.bit_type not in BIT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid bit_type: {data.bit_type}. Must be one of: {', '.join(BIT_TYPES)}",
        )

    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        if data.bit_type == "email":
            if not data.email:
                raise HTTPException(
                    status_code=400, detail="email field required for email bit"
                )
            await cur.execute(
                sql_insert_email(),
                {
                    "persona_id": persona_id,
                    "email": data.email,
                    "name": data.name,
                    "memo": data.memo,
                    "is_primary": data.is_primary,
                    "bit_sequence": data.bit_sequence,
                },
            )

        elif data.bit_type == "phone":
            if not data.number:
                raise HTTPException(
                    status_code=400, detail="number field required for phone bit"
                )
            await cur.execute(
                sql_insert_phone(),
                {
                    "persona_id": persona_id,
                    "number": data.number,
                    "name": data.name,
                    "memo": data.memo,
                    "is_primary": data.is_primary,
                    "bit_sequence": data.bit_sequence,
                },
            )

        elif data.bit_type == "address":
            await cur.execute(
                sql_insert_address(),
                {
                    "persona_id": persona_id,
                    "address1": data.address1,
                    "address2": data.address2,
                    "city": data.city,
                    "state": data.state,
                    "zip": data.zip,
                    "country": data.country,
                    "name": data.name,
                    "memo": data.memo,
                    "is_primary": data.is_primary,
                    "bit_sequence": data.bit_sequence,
                },
            )

        elif data.bit_type == "url":
            if not data.url:
                raise HTTPException(
                    status_code=400, detail="url field required for url bit"
                )
            # Encrypt password if provided
            password_enc = None
            if data.password:
                if not crypto.is_initialized():
                    raise HTTPException(
                        status_code=500,
                        detail="Encryption not configured - cannot store passwords",
                    )
                password_enc = crypto.encrypt_password(data.password)

            await cur.execute(
                sql_insert_url(),
                {
                    "persona_id": persona_id,
                    "url": data.url,
                    "username": data.username,
                    "password_enc": password_enc,
                    "pw_reset_dt": data.pw_reset_dt,
                    "pw_next_reset_dt": data.pw_next_reset_dt,
                    "name": data.name,
                    "memo": data.memo,
                    "is_primary": data.is_primary,
                    "bit_sequence": data.bit_sequence,
                },
            )

        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create contact bit")
        return row["id"]


async def _update_bit(
    conn: psycopg.AsyncConnection,
    bit_id: UUID,
    bit_type: str,
    data: BitUpdate,
) -> int:
    """Update an existing contact bit."""
    table = BIT_TYPE_TABLES[bit_type]

    # Build dynamic update
    updates = []
    params: dict = {"id": bit_id}

    # Common fields
    if data.name is not None:
        updates.append("name = %(name)s")
        params["name"] = data.name
    if data.memo is not None:
        updates.append("memo = %(memo)s")
        params["memo"] = data.memo
    if data.is_primary is not None:
        updates.append("is_primary = %(is_primary)s")
        params["is_primary"] = data.is_primary
    if data.bit_sequence is not None:
        updates.append("bit_sequence = %(bit_sequence)s")
        params["bit_sequence"] = data.bit_sequence

    # Type-specific fields
    if bit_type == "email" and data.email is not None:
        updates.append("email = %(email)s")
        params["email"] = data.email

    elif bit_type == "phone" and data.number is not None:
        updates.append("number = %(number)s")
        params["number"] = data.number

    elif bit_type == "address":
        if data.address1 is not None:
            updates.append("address1 = %(address1)s")
            params["address1"] = data.address1
        if data.address2 is not None:
            updates.append("address2 = %(address2)s")
            params["address2"] = data.address2
        if data.city is not None:
            updates.append("city = %(city)s")
            params["city"] = data.city
        if data.state is not None:
            updates.append("state = %(state)s")
            params["state"] = data.state
        if data.zip is not None:
            updates.append("zip = %(zip)s")
            params["zip"] = data.zip
        if data.country is not None:
            updates.append("country = %(country)s")
            params["country"] = data.country

    elif bit_type == "url":
        if data.url is not None:
            updates.append("url = %(url)s")
            params["url"] = data.url
        if data.username is not None:
            updates.append("username = %(username)s")
            params["username"] = data.username
        if data.password is not None:
            # Setting a new password
            if not crypto.is_initialized():
                raise HTTPException(
                    status_code=500,
                    detail="Encryption not configured - cannot store passwords",
                )
            updates.append("password_enc = %(password_enc)s")
            params["password_enc"] = crypto.encrypt_password(data.password)
            # Auto-set pw_reset_dt to today if not explicitly provided
            if data.pw_reset_dt is None:
                updates.append("pw_reset_dt = %(pw_reset_dt)s")
                params["pw_reset_dt"] = date.today()
        elif data.clear_password:
            # Clearing the password (only if not setting a new one)
            updates.append("password_enc = NULL")
        if data.pw_reset_dt is not None:
            updates.append("pw_reset_dt = %(pw_reset_dt)s")
            params["pw_reset_dt"] = data.pw_reset_dt
        if data.pw_next_reset_dt is not None:
            updates.append("pw_next_reset_dt = %(pw_next_reset_dt)s")
            params["pw_next_reset_dt"] = data.pw_next_reset_dt

    if not updates:
        return 1  # Nothing to update, but not an error

    return await db.execute(
        conn,
        sql_update_bit(table, updates),
        params,
    )


# Column definitions for persona shares
PERSONA_SHARE_COLUMNS = [
    ColumnMeta(key="user", label="User", type="ref"),
    ColumnMeta(key="is_owner", label="Owner", type="boolean"),
]


async def _get_persona_shares(
    conn: psycopg.AsyncConnection, persona_id: UUID
) -> MultiRowResponse:
    """Get list of users who have access to a persona."""
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            sql_select_persona_shares(),
            {"persona_id": persona_id},
        )
        rows = await cur.fetchall()

    data = [
        {
            "user": {"id": str(row["user_id"]), "name": row["full_name"] or row["username"]},
            "is_owner": row["is_owner"],
        }
        for row in rows
    ]

    return MultiRowResponse(columns=PERSONA_SHARE_COLUMNS, data=data)


class ContactsController(Controller):
    path = "/api/contacts"
    tags = ["contacts"]

    @get(guards=[require_capability("contacts:read")])
    async def list_contacts(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        search: str | None = Parameter(default=None, description="Search query"),
        limit: int = Parameter(default=50, le=500, ge=1),
        offset: int = Parameter(default=0, ge=0),
    ) -> MultiRowResponse:
        """List all contacts accessible to the current user."""
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                sql_select_personas(filter_search=True),
                {
                    "user_id": current_user.id,
                    "search": search,
                    "limit": limit,
                    "offset": offset,
                },
            )
            rows = await cur.fetchall()
            return MultiRowResponse(
                columns=PERSONA_LIST_COLUMNS,
                data=[dict(row) for row in rows],
            )

    @get("/{contact_id:uuid}", guards=[require_capability("contacts:read")])
    async def get_contact(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
    ) -> SingleRowResponse:
        """Get a single contact with all contact info."""
        return await _get_persona_by_id(conn, contact_id, current_user.id)

    @post(status_code=201, guards=[require_capability("contacts:write")])
    async def create_contact(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        data: PersonaCreate,
    ) -> SingleRowResponse:
        """Create a new contact."""
        # Validate corporate entity constraints
        if data.is_corporate:
            if data.first_name is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Corporate entities cannot have a first name",
                )
            if data.title is not None:
                raise HTTPException(
                    status_code=400, detail="Corporate entities cannot have a title"
                )
            if len(data.last_name) < 2:
                raise HTTPException(
                    status_code=400,
                    detail="Corporate name must be at least 2 characters",
                )
        else:
            # Individual: must have either first or last name >= 2 chars
            has_valid_last = data.last_name and len(data.last_name) >= 2
            has_valid_first = data.first_name and len(data.first_name) >= 2
            if not has_valid_last and not has_valid_first:
                raise HTTPException(
                    status_code=400,
                    detail="Individual must have first or last name of at least 2 characters",
                )

        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            # Use a transaction to handle the deferred constraint
            await cur.execute("BEGIN")
            try:
                # Insert persona
                await cur.execute(
                    sql_insert_persona(),
                    {
                        "is_corporate": data.is_corporate,
                        "last_name": data.last_name,
                        "first_name": data.first_name,
                        "title": data.title,
                        "organization": data.organization,
                        "memo": data.memo,
                        "birthday": data.birthday,
                        "anniversary": data.anniversary,
                        "owner_id": current_user.id,
                    },
                )
                row = await cur.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=500, detail="Failed to create contact"
                    )
                persona_id = row["id"]

                # Insert into persona_shares for the owner
                await cur.execute(
                    sql_insert_persona_share(),
                    {"persona_id": persona_id, "user_id": current_user.id},
                )

                await cur.execute("COMMIT")
            except Exception:
                await cur.execute("ROLLBACK")
                raise

        return await _get_persona_by_id(conn, persona_id, current_user.id)

    @put("/{contact_id:uuid}", guards=[require_capability("contacts:write")])
    async def update_contact(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
        data: PersonaUpdate,
    ) -> SingleRowResponse:
        """Update an existing contact. Only the owner can update."""
        await _verify_persona_access(conn, contact_id, current_user.id, require_owner=True)

        # Build dynamic update query
        fields: set[str] = set()
        params: dict = {"id": contact_id}

        if data.is_corporate is not None:
            fields.add("is_corporate")
            params["is_corporate"] = data.is_corporate
        if data.last_name is not None:
            fields.add("last_name")
            params["last_name"] = data.last_name
        if data.first_name is not None:
            fields.add("first_name")
            params["first_name"] = data.first_name
        if data.title is not None:
            fields.add("title")
            params["title"] = data.title
        if data.organization is not None:
            fields.add("organization")
            params["organization"] = data.organization
        if data.memo is not None:
            fields.add("memo")
            params["memo"] = data.memo
        if data.birthday is not None:
            fields.add("birthday")
            params["birthday"] = data.birthday
        if data.anniversary is not None:
            fields.add("anniversary")
            params["anniversary"] = data.anniversary

        if not fields:
            return await _get_persona_by_id(conn, contact_id, current_user.id)

        await db.execute(
            conn,
            sql_update_persona(fields),
            params,
        )

        return await _get_persona_by_id(conn, contact_id, current_user.id)

    @delete("/{contact_id:uuid}", status_code=204, guards=[require_capability("contacts:write")])
    async def delete_contact(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
    ) -> None:
        """Delete a contact and all associated bits. Only the owner can delete."""
        await _verify_persona_access(conn, contact_id, current_user.id, require_owner=True)

        # Delete persona_shares first (due to FK constraint)
        await db.execute(conn, sql_delete_persona_shares(), {"id": contact_id})

        # Delete all bits (they have ON DELETE CASCADE, but let's be explicit)
        await db.execute(conn, sql_delete_email_addresses(), {"id": contact_id})
        await db.execute(conn, sql_delete_phone_numbers(), {"id": contact_id})
        await db.execute(conn, sql_delete_street_addresses(), {"id": contact_id})
        await db.execute(conn, sql_delete_urls(), {"id": contact_id})

        # Delete the persona
        await db.execute(conn, sql_delete_persona(), {"id": contact_id})

    # -------------------------------------------------------------------------
    # Contact Bits Endpoints
    # -------------------------------------------------------------------------

    @post("/{contact_id:uuid}/bits", status_code=201, guards=[require_capability("contacts:write")])
    async def create_bit(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
        data: BitCreate,
    ) -> SingleRowResponse:
        """Add a new contact bit (email, phone, address, or URL). Owner only."""
        await _verify_persona_access(conn, contact_id, current_user.id, require_owner=True)
        await _insert_bit(conn, contact_id, data)
        return await _get_persona_by_id(conn, contact_id, current_user.id)

    @put("/{contact_id:uuid}/bits/{bit_id:uuid}", guards=[require_capability("contacts:write")])
    async def update_bit(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
        bit_id: UUID,
        data: BitUpdate,
    ) -> SingleRowResponse:
        """Update an existing contact bit. Owner only."""
        await _verify_persona_access(conn, contact_id, current_user.id, require_owner=True)

        # Determine which table the bit is in
        bit_type = await _get_bit_type(conn, bit_id)
        if not bit_type:
            raise HTTPException(status_code=404, detail="Contact bit not found")

        # Verify the bit belongs to this persona
        table = BIT_TYPE_TABLES[bit_type]
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_bit_persona_id(table),
                {"id": bit_id},
            )
            row = await cur.fetchone()
            if not row or row[0] != contact_id:
                raise HTTPException(
                    status_code=404, detail="Contact bit not found for this contact"
                )

        count = await _update_bit(conn, bit_id, bit_type, data)
        if count == 0:
            raise HTTPException(status_code=404, detail="Contact bit not found")

        return await _get_persona_by_id(conn, contact_id, current_user.id)

    @delete("/{contact_id:uuid}/bits/{bit_id:uuid}", status_code=204, guards=[require_capability("contacts:write")])
    async def delete_bit(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
        bit_id: UUID,
    ) -> None:
        """Remove a contact bit. Owner only."""
        await _verify_persona_access(conn, contact_id, current_user.id, require_owner=True)

        # Determine which table the bit is in
        bit_type = await _get_bit_type(conn, bit_id)
        if not bit_type:
            raise HTTPException(status_code=404, detail="Contact bit not found")

        # Verify the bit belongs to this persona and delete
        table = BIT_TYPE_TABLES[bit_type]
        count = await db.execute(
            conn,
            sql_delete_bit(table),
            {"id": bit_id, "persona_id": contact_id},
        )
        if count == 0:
            raise HTTPException(
                status_code=404, detail="Contact bit not found for this contact"
            )

    @post("/{contact_id:uuid}/bits/reorder", guards=[require_capability("contacts:write")])
    async def reorder_bits(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
        data: BitReorderRequest,
    ) -> SingleRowResponse:
        """Bulk update bit sequences for reordering. Owner only."""
        await _verify_persona_access(conn, contact_id, current_user.id, require_owner=True)

        for item in data.items:
            bit_id = UUID(item.id)
            bit_type = await _get_bit_type(conn, bit_id)
            if not bit_type:
                raise HTTPException(
                    status_code=404, detail=f"Contact bit not found: {item.id}"
                )

            table = BIT_TYPE_TABLES[bit_type]
            count = await db.execute(
                conn,
                sql_update_bit_sequence(table),
                {
                    "id": bit_id,
                    "bit_sequence": item.bit_sequence,
                    "persona_id": contact_id,
                },
            )
            if count == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Contact bit not found for this contact: {item.id}",
                )

        return await _get_persona_by_id(conn, contact_id, current_user.id)

    @get("/{contact_id:uuid}/bits/{bit_id:uuid}", guards=[require_capability("contacts:read")])
    async def get_bit(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
        bit_id: UUID,
    ) -> SingleRowResponse:
        """Get a single contact bit by ID."""
        await _verify_persona_access(conn, contact_id, current_user.id)

        # Determine which table the bit is in
        bit_type = await _get_bit_type(conn, bit_id)
        if not bit_type:
            raise HTTPException(status_code=404, detail="Contact bit not found")

        # Verify the bit belongs to this persona
        table = BIT_TYPE_TABLES[bit_type]
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                sql_select_bit_persona_id(table),
                {"id": bit_id},
            )
            row = await cur.fetchone()
            if not row or row["persona_id"] != contact_id:
                raise HTTPException(
                    status_code=404, detail="Contact bit not found for this contact"
                )

        # Fetch the bit from the unified view
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                sql_select_bit_by_id(),
                {"bit_id": bit_id, "persona_id": contact_id},
            )
            row = await cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Contact bit not found")

        # Normalize bit_type and merge bit_data
        view_bit_type = row["bit_type"]
        api_bit_type = VIEW_BIT_TYPE_MAP.get(view_bit_type, view_bit_type)

        bit: dict = {
            "id": row["id"],
            "bit_type": api_bit_type,
            "name": row["name"],
            "memo": row["memo"],
            "is_primary": row["is_primary"],
            "bit_sequence": row["bit_sequence"],
        }

        if row["bit_data"]:
            bit_data = dict(row["bit_data"])
            # For URL bits: extract password info but never expose password_enc
            if api_bit_type == "url":
                password_enc = bit_data.pop("password_enc", None)
                bit["has_password"] = password_enc is not None
            bit.update(bit_data)

        # Define columns for single bit response
        bit_columns = [
            ColumnMeta(key="id", label="ID", type="uuid"),
            ColumnMeta(key="bit_type", label="Type", type="string"),
            ColumnMeta(key="name", label="Label", type="string"),
            ColumnMeta(key="memo", label="Memo", type="string"),
            ColumnMeta(key="is_primary", label="Primary", type="boolean"),
            ColumnMeta(key="bit_sequence", label="Sequence", type="number"),
        ]

        return SingleRowResponse(columns=bit_columns, data=bit)

    @get("/{contact_id:uuid}/bits/{bit_id:uuid}/password", guards=[require_capability("contacts:passwords")])
    async def get_password(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
        bit_id: UUID,
    ) -> SingleRowResponse:
        """Decrypt and return a URL bit's password.

        Only URL bits can have passwords. Returns 404 if the bit doesn't exist,
        isn't a URL bit, or has no password set.
        """
        await _verify_persona_access(conn, contact_id, current_user.id)

        # Only URL bits have passwords
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                sql_select_url_password(),
                {"bit_id": bit_id, "persona_id": contact_id},
            )
            row = await cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=404, detail="URL bit not found for this contact"
            )

        if not row["password_enc"]:
            raise HTTPException(status_code=404, detail="No password set for this URL")

        if not crypto.is_initialized():
            raise HTTPException(
                status_code=500, detail="Encryption not configured - cannot decrypt"
            )

        password = crypto.decrypt_password(row["password_enc"])
        return SingleRowResponse(
            columns=[ColumnMeta(key="password", label="Password", type="string")],
            data={"password": password},
        )

    # -------------------------------------------------------------------------
    # Sharing Endpoints
    # -------------------------------------------------------------------------

    @get("/{contact_id:uuid}/shares", guards=[require_capability("contacts:read")])
    async def list_shares(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
    ) -> MultiRowResponse:
        """List all users who have access to this contact."""
        await _verify_persona_access(conn, contact_id, current_user.id)
        return await _get_persona_shares(conn, contact_id)

    @post("/{contact_id:uuid}/shares", status_code=201, guards=[require_capability("contacts:write")])
    async def add_share(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
        data: dict,
    ) -> MultiRowResponse:
        """Share a contact with another user. Owner only."""
        await _verify_persona_access(conn, contact_id, current_user.id, require_owner=True)

        user_id = data.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        # Verify target user exists
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_user_exists_active(),
                {"user_id": user_id},
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

        # Add share (ignore if already shared)
        await db.execute(
            conn,
            sql_insert_persona_share(),
            {"persona_id": contact_id, "user_id": user_id},
        )

        return await _get_persona_shares(conn, contact_id)

    @delete("/{contact_id:uuid}/shares/{user_id:uuid}", status_code=204, guards=[require_capability("contacts:write")])
    async def remove_share(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
        user_id: UUID,
    ) -> None:
        """Remove a user's access to a contact. Owner only."""
        await _verify_persona_access(conn, contact_id, current_user.id, require_owner=True)

        # Cannot remove owner's share
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_persona_owner(),
                {"id": contact_id},
            )
            row = await cur.fetchone()
            if row and str(row[0]) == str(user_id):
                raise HTTPException(
                    status_code=400, detail="Cannot remove owner's access"
                )

        count = await db.execute(
            conn,
            sql_delete_persona_share(),
            {"persona_id": contact_id, "user_id": user_id},
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="Share not found")

    @post("/{contact_id:uuid}/transfer-ownership", guards=[require_capability("contacts:write")])
    async def transfer_ownership(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        contact_id: UUID,
        data: dict,
    ) -> SingleRowResponse:
        """Transfer ownership to another user. Current owner becomes shared user."""
        await _verify_persona_access(conn, contact_id, current_user.id, require_owner=True)

        new_owner_id = data.get("new_owner_id")
        if not new_owner_id:
            raise HTTPException(status_code=400, detail="new_owner_id is required")

        if str(new_owner_id) == current_user.id:
            raise HTTPException(status_code=400, detail="Already the owner")

        # Verify new owner exists
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_user_exists_active(),
                {"user_id": new_owner_id},
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

        # Ensure new owner is in shares
        await db.execute(
            conn,
            sql_insert_persona_share(),
            {"persona_id": contact_id, "user_id": new_owner_id},
        )

        # Transfer ownership
        await db.execute(
            conn,
            sql_update_persona_owner(),
            {"id": contact_id, "new_owner_id": new_owner_id},
        )

        return await _get_persona_by_id(conn, contact_id, current_user.id)
