from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

import psycopg
import psycopg.rows
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException
from litestar.params import Parameter

import core.crypto as crypto
import core.db as db
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse


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


# Column definitions for persona list (summary view)
PERSONA_LIST_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="entity_name", label="Name", type="string"),
    ColumnMeta(key="is_corporate", label="Corporate", type="boolean"),
    ColumnMeta(key="organization", label="Organization", type="string"),
    ColumnMeta(key="primary_email", label="Email", type="string"),
    ColumnMeta(key="primary_phone", label="Phone", type="string"),
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


@dataclass
class BitReorderItem:
    """Single item in reorder request."""

    id: str  # UUID as string
    bit_sequence: int


@dataclass
class BitReorderRequest:
    """Bulk reorder contact bits."""

    items: list[BitReorderItem]


# TODO: Replace with session-based authentication
# For now, use a test owner ID for development
TEST_OWNER_ID = "00000000-0000-0000-0000-000000000001"


async def _get_bits_for_persona(
    conn: psycopg.AsyncConnection, persona_id: UUID
) -> list[dict]:
    """Fetch all contact bits for a persona."""
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
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
            """,
            {"persona_id": persona_id},
        )
        rows = await cur.fetchall()
        bits = []
        for row in rows:
            bit = {
                "id": row["id"],
                "bit_type": row["bit_type"],
                "name": row["name"],
                "memo": row["memo"],
                "is_primary": row["is_primary"],
                "bit_sequence": row["bit_sequence"],
            }
            # Merge bit_data fields into the bit object
            if row["bit_data"]:
                # Filter out password_enc from URL bits (never expose to frontend)
                bit_data = dict(row["bit_data"])
                bit_data.pop("password_enc", None)
                bit.update(bit_data)
            bits.append(bit)
        return bits


async def _get_persona_by_id(
    conn: psycopg.AsyncConnection, persona_id: UUID, owner_id: str
) -> SingleRowResponse:
    """Get a single persona with all its bits."""
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
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
            """,
            {"id": persona_id, "owner_id": owner_id},
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")

        data = dict(row)
        data["bits"] = await _get_bits_for_persona(conn, persona_id)

        return SingleRowResponse(columns=PERSONA_DETAIL_COLUMNS, data=data)


async def _verify_persona_ownership(
    conn: psycopg.AsyncConnection, persona_id: UUID, owner_id: str
) -> None:
    """Verify that a persona exists and belongs to the owner."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id FROM contacts.personas
            WHERE id = %(id)s AND owner_id = %(owner_id)s
            """,
            {"id": persona_id, "owner_id": owner_id},
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")


async def _get_bit_type(conn: psycopg.AsyncConnection, bit_id: UUID) -> str | None:
    """Determine which table a bit belongs to by checking all bit tables."""
    async with conn.cursor() as cur:
        for bit_type, table in BIT_TYPE_TABLES.items():
            await cur.execute(
                f"SELECT id FROM {table} WHERE id = %(id)s",
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
                """
                INSERT INTO contacts.email_addresses
                    (persona_id, email, name, memo, is_primary, bit_sequence)
                VALUES
                    (%(persona_id)s, %(email)s, %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
                RETURNING id
                """,
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
                """
                INSERT INTO contacts.phone_numbers
                    (persona_id, number, name, memo, is_primary, bit_sequence)
                VALUES
                    (%(persona_id)s, %(number)s, %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
                RETURNING id
                """,
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
                """
                INSERT INTO contacts.street_addresses
                    (persona_id, address1, address2, city, state, zip, country,
                     name, memo, is_primary, bit_sequence)
                VALUES
                    (%(persona_id)s, %(address1)s, %(address2)s, %(city)s, %(state)s,
                     %(zip)s, %(country)s, %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
                RETURNING id
                """,
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
                """
                INSERT INTO contacts.urls
                    (persona_id, url, username, password_enc, name, memo, is_primary, bit_sequence)
                VALUES
                    (%(persona_id)s, %(url)s, %(username)s, %(password_enc)s,
                     %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
                RETURNING id
                """,
                {
                    "persona_id": persona_id,
                    "url": data.url,
                    "username": data.username,
                    "password_enc": password_enc,
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
            if not crypto.is_initialized():
                raise HTTPException(
                    status_code=500,
                    detail="Encryption not configured - cannot store passwords",
                )
            updates.append("password_enc = %(password_enc)s")
            params["password_enc"] = crypto.encrypt_password(data.password)

    if not updates:
        return 1  # Nothing to update, but not an error

    return await db.execute(
        conn,
        f"UPDATE {table} SET {', '.join(updates)} WHERE id = %(id)s",
        params,
    )


class ContactsController(Controller):
    path = "/api/contacts"
    tags = ["contacts"]

    @get()
    async def list_contacts(
        self,
        conn: psycopg.AsyncConnection,
        search: str | None = Parameter(default=None, description="Search query"),
        limit: int = Parameter(default=50, le=500, ge=1),
        offset: int = Parameter(default=0, ge=0),
    ) -> MultiRowResponse:
        """List all contacts with optional search."""
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                """
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
                    ) AS primary_phone
                FROM contacts.personas p
                JOIN contacts.personas_calc pc ON pc.id = p.id
                WHERE
                    p.owner_id = %(owner_id)s
                    AND (
                        %(search)s::text IS NULL
                        OR pc.fts_search @@ websearch_to_tsquery('english', %(search)s)
                    )
                ORDER BY pc.entity_name
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                {
                    "owner_id": TEST_OWNER_ID,
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

    @get("/{contact_id:uuid}")
    async def get_contact(
        self,
        conn: psycopg.AsyncConnection,
        contact_id: UUID,
    ) -> SingleRowResponse:
        """Get a single contact with all contact info."""
        return await _get_persona_by_id(conn, contact_id, TEST_OWNER_ID)

    @post(status_code=201)
    async def create_contact(
        self,
        conn: psycopg.AsyncConnection,
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
                    """
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
                    """,
                    {
                        "is_corporate": data.is_corporate,
                        "last_name": data.last_name,
                        "first_name": data.first_name,
                        "title": data.title,
                        "organization": data.organization,
                        "memo": data.memo,
                        "birthday": data.birthday,
                        "anniversary": data.anniversary,
                        "owner_id": TEST_OWNER_ID,
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
                    """
                    INSERT INTO contacts.persona_shares (persona_id, user_id)
                    VALUES (%(persona_id)s, %(user_id)s)
                    """,
                    {"persona_id": persona_id, "user_id": TEST_OWNER_ID},
                )

                await cur.execute("COMMIT")
            except Exception:
                await cur.execute("ROLLBACK")
                raise

        return await _get_persona_by_id(conn, persona_id, TEST_OWNER_ID)

    @put("/{contact_id:uuid}")
    async def update_contact(
        self,
        conn: psycopg.AsyncConnection,
        contact_id: UUID,
        data: PersonaUpdate,
    ) -> SingleRowResponse:
        """Update an existing contact."""
        # Build dynamic update query
        updates = []
        params: dict = {"id": contact_id, "owner_id": TEST_OWNER_ID}

        if data.is_corporate is not None:
            updates.append("corporate_entity = %(is_corporate)s")
            params["is_corporate"] = data.is_corporate
        if data.last_name is not None:
            updates.append("l_name = %(last_name)s")
            params["last_name"] = data.last_name
        if data.first_name is not None:
            updates.append("f_name = %(first_name)s")
            params["first_name"] = data.first_name
        if data.title is not None:
            updates.append("title = %(title)s")
            params["title"] = data.title
        if data.organization is not None:
            updates.append("organization = %(organization)s")
            params["organization"] = data.organization
        if data.memo is not None:
            updates.append("memo = %(memo)s")
            params["memo"] = data.memo
        if data.birthday is not None:
            updates.append("birthday = %(birthday)s")
            params["birthday"] = data.birthday
        if data.anniversary is not None:
            updates.append("anniversary = %(anniversary)s")
            params["anniversary"] = data.anniversary

        if not updates:
            return await _get_persona_by_id(conn, contact_id, TEST_OWNER_ID)

        count = await db.execute(
            conn,
            f"""
            UPDATE contacts.personas
            SET {", ".join(updates)}
            WHERE id = %(id)s AND owner_id = %(owner_id)s
            """,
            params,
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="Contact not found")

        return await _get_persona_by_id(conn, contact_id, TEST_OWNER_ID)

    @delete("/{contact_id:uuid}", status_code=204)
    async def delete_contact(
        self,
        conn: psycopg.AsyncConnection,
        contact_id: UUID,
    ) -> None:
        """Delete a contact and all associated bits."""
        # Check if contact exists and belongs to owner
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id FROM contacts.personas
                WHERE id = %(id)s AND owner_id = %(owner_id)s
                """,
                {"id": contact_id, "owner_id": TEST_OWNER_ID},
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Contact not found")

        # Delete persona_shares first (due to FK constraint)
        await db.execute(
            conn,
            "DELETE FROM contacts.persona_shares WHERE persona_id = %(id)s",
            {"id": contact_id},
        )

        # Delete all bits (they have ON DELETE CASCADE, but let's be explicit)
        await db.execute(
            conn,
            "DELETE FROM contacts.email_addresses WHERE persona_id = %(id)s",
            {"id": contact_id},
        )
        await db.execute(
            conn,
            "DELETE FROM contacts.phone_numbers WHERE persona_id = %(id)s",
            {"id": contact_id},
        )
        await db.execute(
            conn,
            "DELETE FROM contacts.street_addresses WHERE persona_id = %(id)s",
            {"id": contact_id},
        )
        await db.execute(
            conn,
            "DELETE FROM contacts.urls WHERE persona_id = %(id)s",
            {"id": contact_id},
        )

        # Delete the persona
        count = await db.execute(
            conn,
            """
            DELETE FROM contacts.personas
            WHERE id = %(id)s AND owner_id = %(owner_id)s
            """,
            {"id": contact_id, "owner_id": TEST_OWNER_ID},
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="Contact not found")

    # -------------------------------------------------------------------------
    # Contact Bits Endpoints
    # -------------------------------------------------------------------------

    @post("/{contact_id:uuid}/bits", status_code=201)
    async def create_bit(
        self,
        conn: psycopg.AsyncConnection,
        contact_id: UUID,
        data: BitCreate,
    ) -> SingleRowResponse:
        """Add a new contact bit (email, phone, address, or URL)."""
        await _verify_persona_ownership(conn, contact_id, TEST_OWNER_ID)
        await _insert_bit(conn, contact_id, data)
        return await _get_persona_by_id(conn, contact_id, TEST_OWNER_ID)

    @put("/{contact_id:uuid}/bits/{bit_id:uuid}")
    async def update_bit(
        self,
        conn: psycopg.AsyncConnection,
        contact_id: UUID,
        bit_id: UUID,
    data: BitUpdate,
    ) -> SingleRowResponse:
        """Update an existing contact bit."""
        await _verify_persona_ownership(conn, contact_id, TEST_OWNER_ID)

        # Determine which table the bit is in
        bit_type = await _get_bit_type(conn, bit_id)
        if not bit_type:
            raise HTTPException(status_code=404, detail="Contact bit not found")

        # Verify the bit belongs to this persona
        table = BIT_TYPE_TABLES[bit_type]
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT persona_id FROM {table} WHERE id = %(id)s",
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

        return await _get_persona_by_id(conn, contact_id, TEST_OWNER_ID)

    @delete("/{contact_id:uuid}/bits/{bit_id:uuid}", status_code=204)
    async def delete_bit(
        self,
        conn: psycopg.AsyncConnection,
        contact_id: UUID,
        bit_id: UUID,
    ) -> None:
        """Remove a contact bit."""
        await _verify_persona_ownership(conn, contact_id, TEST_OWNER_ID)

        # Determine which table the bit is in
        bit_type = await _get_bit_type(conn, bit_id)
        if not bit_type:
            raise HTTPException(status_code=404, detail="Contact bit not found")

        # Verify the bit belongs to this persona and delete
        table = BIT_TYPE_TABLES[bit_type]
        count = await db.execute(
            conn,
            f"DELETE FROM {table} WHERE id = %(id)s AND persona_id = %(persona_id)s",
            {"id": bit_id, "persona_id": contact_id},
        )
        if count == 0:
            raise HTTPException(
                status_code=404, detail="Contact bit not found for this contact"
            )

    @post("/{contact_id:uuid}/bits/reorder")
    async def reorder_bits(
        self,
        conn: psycopg.AsyncConnection,
        contact_id: UUID,
        data: BitReorderRequest,
    ) -> SingleRowResponse:
        """Bulk update bit sequences for reordering."""
        await _verify_persona_ownership(conn, contact_id, TEST_OWNER_ID)

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
                f"""
                UPDATE {table}
                SET bit_sequence = %(bit_sequence)s
                WHERE id = %(id)s AND persona_id = %(persona_id)s
                """,
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

        return await _get_persona_by_id(conn, contact_id, TEST_OWNER_ID)
