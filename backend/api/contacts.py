from dataclasses import dataclass
from datetime import date
from uuid import UUID

import psycopg
import psycopg.rows
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException
from litestar.params import Parameter

import core.db as db
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse


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
                        %(search)s IS NULL
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
