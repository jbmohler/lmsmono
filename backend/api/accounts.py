import datetime
from dataclasses import dataclass
from uuid import UUID

import psycopg
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException
from litestar.params import Parameter

import core.db as db
from core.guards import require_capability
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse, make_ref


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------


def sql_select_account_types() -> str:
    """List all account types."""
    return """
        SELECT id, atype_name, description, balance_sheet, debit, retained_earnings
        FROM hacc.accounttypes
        ORDER BY sort
    """


def sql_select_accounts() -> str:
    """List all accounts with type and journal info."""
    return """
        SELECT
            a.id,
            a.acc_name,
            a.description,
            t.id AS account_type_id,
            t.atype_name AS account_type_name,
            j.id AS journal_id,
            j.jrn_name AS journal_name,
            a.retearn_id AS retearn_id,
            r.acc_name AS retearn_name
        FROM hacc.accounts a
        JOIN hacc.accounttypes t ON a.type_id = t.id
        JOIN hacc.journals j ON a.journal_id = j.id
        LEFT JOIN hacc.accounts r ON r.id = a.retearn_id
        ORDER BY t.sort, a.acc_name
    """


def sql_select_account_by_id() -> str:
    """Get a single account by ID with joins (includes extra detail fields)."""
    return """
        SELECT
            a.id,
            a.acc_name,
            a.description,
            t.id AS account_type_id,
            t.atype_name AS account_type_name,
            j.id AS journal_id,
            j.jrn_name AS journal_name,
            a.retearn_id AS retearn_id,
            r.acc_name AS retearn_name,
            a.acc_note,
            a.rec_note,
            a.contact_keywords,
            a.instname,
            a.instaddr1,
            a.instaddr2,
            a.instcity,
            a.inststate,
            a.instzip
        FROM hacc.accounts a
        JOIN hacc.accounttypes t ON a.type_id = t.id
        JOIN hacc.journals j ON a.journal_id = j.id
        LEFT JOIN hacc.accounts r ON r.id = a.retearn_id
        WHERE a.id = %(id)s
    """


def sql_select_account_transactions(date_from: bool = False) -> str:
    """Get transactions for a specific account."""
    date_filter = "AND t.trandate >= %(from_date)s" if date_from else ""
    return f"""
        SELECT
            t.tid AS id,
            t.trandate,
            t.tranref,
            t.payee,
            t.memo,
            s.sum
        FROM hacc.transactions t
        JOIN hacc.splits s ON s.stid = t.tid
        WHERE s.account_id = %(account_id)s
            {date_filter}
        ORDER BY t.trandate DESC, t.tid DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """


def sql_select_account_splits_count() -> str:
    """Count splits using an account (for delete check)."""
    return """
        SELECT COUNT(*) FROM hacc.splits
        WHERE account_id = %(id)s
    """


def sql_insert_account() -> str:
    """Create a new account."""
    return """
        INSERT INTO hacc.accounts (acc_name, type_id, journal_id, description, retearn_id)
        VALUES (%(acc_name)s, %(type_id)s, %(journal_id)s, %(description)s, %(retearn_id)s)
        RETURNING id
    """


def sql_update_account(fields: set[str]) -> str:
    """Update account fields dynamically."""
    valid_fields = {"acc_name", "description", "type_id", "journal_id", "retearn_id"}
    updates = [f"{f} = %({f})s" for f in fields if f in valid_fields]
    if not updates:
        raise ValueError("No valid fields to update")
    return f"""
        UPDATE hacc.accounts
        SET {", ".join(updates)}
        WHERE id = %(id)s
    """


def sql_delete_account() -> str:
    """Delete an account by ID."""
    return "DELETE FROM hacc.accounts WHERE id = %(id)s"


ACCOUNT_TYPE_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="atype_name", label="Name", type="string"),
    ColumnMeta(key="description", label="Description", type="string"),
    ColumnMeta(key="balance_sheet", label="Balance Sheet", type="boolean"),
    ColumnMeta(key="debit", label="Debit", type="boolean"),
    ColumnMeta(key="retained_earnings", label="Retained Earnings Type", type="boolean"),
]

ACCOUNT_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="acc_name", label="Name", type="string"),
    ColumnMeta(key="description", label="Description", type="string"),
    ColumnMeta(key="account_type", label="Type", type="ref"),
    ColumnMeta(key="journal", label="Journal", type="ref"),
    ColumnMeta(key="retained_earnings", label="Retained Earnings", type="ref"),
]

ACCOUNT_DETAIL_COLUMNS = [
    *ACCOUNT_COLUMNS,
    ColumnMeta(key="acc_note", label="Account Note", type="string"),
    ColumnMeta(key="rec_note", label="Reconciliation Note", type="string"),
    ColumnMeta(key="contact_keywords", label="Contact Keywords", type="string"),
    ColumnMeta(key="instname", label="Institution", type="string"),
    ColumnMeta(key="instaddr1", label="Address 1", type="string"),
    ColumnMeta(key="instaddr2", label="Address 2", type="string"),
    ColumnMeta(key="instcity", label="City", type="string"),
    ColumnMeta(key="inststate", label="State", type="string"),
    ColumnMeta(key="instzip", label="Zip", type="string"),
]

# Columns for the account transactions endpoint
ACCOUNT_TRANSACTION_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="trandate", label="Date", type="date"),
    ColumnMeta(key="tranref", label="Reference", type="string"),
    ColumnMeta(key="payee", label="Payee", type="string"),
    ColumnMeta(key="memo", label="Memo", type="string"),
    ColumnMeta(key="debit", label="Debit", type="currency"),
    ColumnMeta(key="credit", label="Credit", type="currency"),
]


def transform_account_row(row: dict) -> dict:
    """Transform a raw account row to include ref structs."""
    result: dict = {
        "id": row["id"],
        "acc_name": row["acc_name"],
        "description": row["description"],
        "account_type": make_ref(str(row["account_type_id"]), row["account_type_name"]),
        "journal": make_ref(str(row["journal_id"]), row["journal_name"]),
    }
    if row.get("retearn_id"):
        result["retained_earnings"] = make_ref(str(row["retearn_id"]), row["retearn_name"])
    else:
        result["retained_earnings"] = None
    return result


def transform_account_detail_row(row: dict) -> dict:
    """Transform a raw account detail row (includes extra fields)."""
    base = transform_account_row(row)
    base.update({
        "acc_note": row["acc_note"],
        "rec_note": row["rec_note"],
        "contact_keywords": row["contact_keywords"],
        "instname": row["instname"],
        "instaddr1": row["instaddr1"],
        "instaddr2": row["instaddr2"],
        "instcity": row["instcity"],
        "inststate": row["inststate"],
        "instzip": row["instzip"],
    })
    return base


def sum_to_debit_credit(sum_value) -> tuple:
    """Convert DB sum to API debit/credit."""
    if sum_value is None:
        return None, None
    if sum_value > 0:
        return sum_value, None
    elif sum_value < 0:
        return None, abs(sum_value)
    return None, None


@dataclass
class AccountCreate:
    acc_name: str
    type_id: str  # UUID
    journal_id: str  # UUID
    description: str | None = None
    retearn_id: str | None = None


@dataclass
class AccountUpdate:
    acc_name: str | None = None
    description: str | None = None
    type_id: str | None = None
    journal_id: str | None = None
    retearn_id: str | None = None


async def _get_account_by_id(
    conn: psycopg.AsyncConnection, account_id: UUID
) -> SingleRowResponse:
    """Get a single account by ID (shared logic)."""
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            sql_select_account_by_id(),
            {"id": account_id},
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")
        return SingleRowResponse(
            columns=ACCOUNT_DETAIL_COLUMNS,
            data=transform_account_detail_row(dict(row)),
        )


class AccountTypesController(Controller):
    path = "/api/account-types"
    tags = ["accounts"]

    @get(guards=[require_capability("accounts:read")])
    async def list_account_types(
        self,
        conn: psycopg.AsyncConnection,
    ) -> MultiRowResponse:
        """List all account types."""
        return await db.select_many(
            conn,
            sql_select_account_types(),
            columns=ACCOUNT_TYPE_COLUMNS,
        )


class AccountsController(Controller):
    path = "/api/accounts"
    tags = ["accounts"]

    @get(guards=[require_capability("accounts:read")])
    async def list_accounts(
        self,
        conn: psycopg.AsyncConnection,
    ) -> MultiRowResponse:
        """List all accounts with type and journal info."""
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql_select_accounts())
            rows = await cur.fetchall()
            data = [transform_account_row(dict(row)) for row in rows]
            return MultiRowResponse(columns=ACCOUNT_COLUMNS, data=data)

    @get("/{account_id:uuid}", guards=[require_capability("accounts:read")])
    async def get_account(
        self,
        conn: psycopg.AsyncConnection,
        account_id: UUID,
    ) -> SingleRowResponse:
        """Get a single account by ID."""
        return await _get_account_by_id(conn, account_id)

    @get("/{account_id:uuid}/transactions", guards=[require_capability("transactions:read")])
    async def get_account_transactions(
        self,
        conn: psycopg.AsyncConnection,
        account_id: UUID,
        limit: int = Parameter(default=50, le=500),
        offset: int = Parameter(default=0, ge=0),
        from_date: datetime.date | None = Parameter(default=None, query="from"),
    ) -> MultiRowResponse:
        """Get transactions for a specific account."""
        params: dict = {"account_id": account_id, "limit": limit, "offset": offset}
        if from_date is not None:
            params["from_date"] = from_date
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                sql_select_account_transactions(date_from=from_date is not None),
                params,
            )
            rows = await cur.fetchall()
            data = []
            for row in rows:
                debit, credit = sum_to_debit_credit(row["sum"])
                data.append({
                    "id": row["id"],
                    "trandate": row["trandate"],
                    "tranref": row["tranref"],
                    "payee": row["payee"],
                    "memo": row["memo"],
                    "debit": debit,
                    "credit": credit,
                })
            return MultiRowResponse(columns=ACCOUNT_TRANSACTION_COLUMNS, data=data)

    @post(status_code=201, guards=[require_capability("accounts:write")])
    async def create_account(
        self,
        conn: psycopg.AsyncConnection,
        data: AccountCreate,
    ) -> SingleRowResponse:
        """Create a new account."""
        row = await db.execute_returning(
            conn,
            sql_insert_account(),
            {
                "acc_name": data.acc_name,
                "type_id": data.type_id,
                "journal_id": data.journal_id,
                "description": data.description,
                "retearn_id": data.retearn_id,
            },
        )
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create account")
        return await _get_account_by_id(conn, row["id"])

    @put("/{account_id:uuid}", guards=[require_capability("accounts:write")])
    async def update_account(
        self,
        conn: psycopg.AsyncConnection,
        account_id: UUID,
        data: AccountUpdate,
    ) -> SingleRowResponse:
        """Update an existing account."""
        fields: set[str] = set()
        params: dict[str, str | UUID | None] = {"id": account_id}
        if data.acc_name is not None:
            fields.add("acc_name")
            params["acc_name"] = data.acc_name
        if data.description is not None:
            fields.add("description")
            params["description"] = data.description
        if data.type_id is not None:
            fields.add("type_id")
            params["type_id"] = data.type_id
        if data.journal_id is not None:
            fields.add("journal_id")
            params["journal_id"] = data.journal_id
        if data.retearn_id is not None:
            fields.add("retearn_id")
            # Empty string means clear the field
            params["retearn_id"] = data.retearn_id if data.retearn_id != "" else None

        if not fields:
            return await _get_account_by_id(conn, account_id)

        count = await db.execute(
            conn,
            sql_update_account(fields),
            params,
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="Account not found")
        return await _get_account_by_id(conn, account_id)

    @delete("/{account_id:uuid}", status_code=204, guards=[require_capability("accounts:write")])
    async def delete_account(
        self,
        conn: psycopg.AsyncConnection,
        account_id: UUID,
    ) -> None:
        """Delete an account. Only succeeds if no transactions reference it."""
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_account_splits_count(),
                {"id": account_id},
            )
            row = await cur.fetchone()
            if row and row[0] > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot delete account: transactions are using it",
                )

        count = await db.execute(
            conn,
            sql_delete_account(),
            {"id": account_id},
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="Account not found")
