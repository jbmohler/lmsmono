from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import psycopg
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException
from litestar.params import Parameter

import core.db as db
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse, make_ref


TRANSACTION_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="trandate", label="Date", type="date"),
    ColumnMeta(key="tranref", label="Reference", type="string"),
    ColumnMeta(key="payee", label="Payee", type="string"),
    ColumnMeta(key="memo", label="Memo", type="string"),
]

SPLIT_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="account", label="Account", type="ref"),
    ColumnMeta(key="debit", label="Debit", type="currency"),
    ColumnMeta(key="credit", label="Credit", type="currency"),
]

# Columns for the transaction detail response (includes splits)
TRANSACTION_DETAIL_COLUMNS = TRANSACTION_COLUMNS + [
    ColumnMeta(key="splits", label="Splits", type="string"),  # Nested array
]


def sum_to_debit_credit(sum_value: Decimal) -> tuple[Decimal | None, Decimal | None]:
    """Convert DB sum to API debit/credit."""
    if sum_value > 0:
        return sum_value, None
    elif sum_value < 0:
        return None, abs(sum_value)
    return None, None


def debit_credit_to_sum(debit: Decimal | None, credit: Decimal | None) -> Decimal:
    """Convert API debit/credit to DB sum."""
    if debit:
        return debit
    elif credit:
        return -credit
    return Decimal(0)


@dataclass
class SplitInput:
    account_id: str  # UUID
    debit: Decimal | None = None
    credit: Decimal | None = None


@dataclass
class TransactionCreate:
    trandate: str  # ISO date
    splits: list[SplitInput]
    tranref: str | None = None
    payee: str | None = None
    memo: str | None = None


@dataclass
class TransactionUpdate:
    trandate: str | None = None
    tranref: str | None = None
    payee: str | None = None
    memo: str | None = None
    splits: list[SplitInput] | None = None


def validate_splits(splits: list[SplitInput]) -> None:
    """Validate that splits balance and are well-formed."""
    if len(splits) < 2:
        raise HTTPException(
            status_code=400,
            detail="Transaction must have at least 2 splits",
        )

    total = Decimal(0)
    for split in splits:
        if split.debit and split.credit:
            raise HTTPException(
                status_code=400,
                detail="Split cannot have both debit and credit",
            )
        if not split.debit and not split.credit:
            raise HTTPException(
                status_code=400,
                detail="Split must have either debit or credit",
            )
        total += debit_credit_to_sum(split.debit, split.credit)

    if total != Decimal(0):
        raise HTTPException(
            status_code=400,
            detail="Transaction does not balance: debits must equal credits",
        )


async def get_transaction_splits(
    conn: psycopg.AsyncConnection,
    transaction_id: UUID,
) -> list[dict]:
    """Get splits for a transaction with account refs."""
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT
                s.sid AS id,
                a.id AS account_id,
                a.acc_name AS account_name,
                s.sum
            FROM hacc.splits s
            JOIN hacc.accounts a ON s.account_id = a.id
            WHERE s.stid = %(transaction_id)s
            ORDER BY s.sid
            """,
            {"transaction_id": transaction_id},
        )
        rows = await cur.fetchall()
        splits = []
        for row in rows:
            debit, credit = sum_to_debit_credit(row["sum"])
            splits.append({
                "id": str(row["id"]),
                "account": make_ref(str(row["account_id"]), row["account_name"]),
                "debit": debit,
                "credit": credit,
            })
        return splits


async def _get_transaction_by_id(
    conn: psycopg.AsyncConnection, transaction_id: UUID
) -> SingleRowResponse:
    """Get a single transaction with its splits (shared logic)."""
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(
            """
            SELECT
                t.tid AS id,
                t.trandate,
                t.tranref,
                t.payee,
                t.memo
            FROM hacc.transactions t
            WHERE t.tid = %(id)s
            """,
            {"id": transaction_id},
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found")

        splits = await get_transaction_splits(conn, transaction_id)
        data = dict(row)
        data["splits"] = splits

        return SingleRowResponse(columns=TRANSACTION_DETAIL_COLUMNS, data=data)


class TransactionsController(Controller):
    path = "/api/transactions"
    tags = ["transactions"]

    @get()
    async def list_transactions(
        self,
        conn: psycopg.AsyncConnection,
        limit: int = Parameter(default=50, le=500),
        offset: int = Parameter(default=0, ge=0),
        q: str | None = Parameter(default=None),
        account_id: str | None = Parameter(default=None),
        from_date: str | None = Parameter(default=None, query="from"),
        to_date: str | None = Parameter(default=None, query="to"),
    ) -> MultiRowResponse:
        """List transactions with optional filters."""
        where_clauses = []
        params: dict = {"limit": limit, "offset": offset}

        if q:
            where_clauses.append(
                "(t.payee ILIKE %(q)s OR t.memo ILIKE %(q)s OR t.tranref ILIKE %(q)s)"
            )
            params["q"] = f"%{q}%"

        if account_id:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM hacc.splits s WHERE s.stid = t.tid AND s.account_id = %(account_id)s)"
            )
            params["account_id"] = account_id

        if from_date:
            where_clauses.append("t.trandate >= %(from_date)s")
            params["from_date"] = from_date

        if to_date:
            where_clauses.append("t.trandate <= %(to_date)s")
            params["to_date"] = to_date

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        return await db.select_many(
            conn,
            f"""
            SELECT
                t.tid AS id,
                t.trandate,
                t.tranref,
                t.payee,
                t.memo
            FROM hacc.transactions t
            WHERE {where_sql}
            ORDER BY t.trandate DESC, t.tid DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            params,
            columns=TRANSACTION_COLUMNS,
        )

    @get("/{transaction_id:uuid}")
    async def get_transaction(
        self,
        conn: psycopg.AsyncConnection,
        transaction_id: UUID,
    ) -> SingleRowResponse:
        """Get a single transaction with its splits."""
        return await _get_transaction_by_id(conn, transaction_id)

    @post(status_code=201)
    async def create_transaction(
        self,
        conn: psycopg.AsyncConnection,
        data: TransactionCreate,
    ) -> SingleRowResponse:
        """Create a new transaction with splits."""
        validate_splits(data.splits)

        # Insert transaction
        row = await db.execute_returning(
            conn,
            """
            INSERT INTO hacc.transactions (trandate, tranref, payee, memo)
            VALUES (%(trandate)s, %(tranref)s, %(payee)s, %(memo)s)
            RETURNING tid
            """,
            {
                "trandate": data.trandate,
                "tranref": data.tranref,
                "payee": data.payee,
                "memo": data.memo,
            },
        )
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create transaction")

        transaction_id: UUID = row["tid"]

        # Insert splits
        async with conn.cursor() as cur:
            for split in data.splits:
                sum_value = debit_credit_to_sum(split.debit, split.credit)
                await cur.execute(
                    """
                    INSERT INTO hacc.splits (stid, account_id, sum)
                    VALUES (%(stid)s, %(account_id)s, %(sum)s)
                    """,
                    {
                        "stid": transaction_id,
                        "account_id": split.account_id,
                        "sum": sum_value,
                    },
                )

        return await _get_transaction_by_id(conn, transaction_id)

    @put("/{transaction_id:uuid}")
    async def update_transaction(
        self,
        conn: psycopg.AsyncConnection,
        transaction_id: UUID,
        data: TransactionUpdate,
    ) -> SingleRowResponse:
        """Update a transaction and optionally replace all splits."""
        # Verify transaction exists
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM hacc.transactions WHERE tid = %(id)s",
                {"id": transaction_id},
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Transaction not found")

        # Update transaction fields if provided
        updates = []
        params: dict = {"id": transaction_id}
        if data.trandate is not None:
            updates.append("trandate = %(trandate)s")
            params["trandate"] = data.trandate
        if data.tranref is not None:
            updates.append("tranref = %(tranref)s")
            params["tranref"] = data.tranref
        if data.payee is not None:
            updates.append("payee = %(payee)s")
            params["payee"] = data.payee
        if data.memo is not None:
            updates.append("memo = %(memo)s")
            params["memo"] = data.memo

        if updates:
            await db.execute(
                conn,
                f"""
                UPDATE hacc.transactions
                SET {", ".join(updates)}
                WHERE tid = %(id)s
                """,
                params,
            )

        # Replace splits if provided
        if data.splits is not None:
            validate_splits(data.splits)

            # Delete existing splits
            await db.execute(
                conn,
                "DELETE FROM hacc.splits WHERE stid = %(id)s",
                {"id": transaction_id},
            )

            # Insert new splits
            async with conn.cursor() as cur:
                for split in data.splits:
                    sum_value = debit_credit_to_sum(split.debit, split.credit)
                    await cur.execute(
                        """
                        INSERT INTO hacc.splits (stid, account_id, sum)
                        VALUES (%(stid)s, %(account_id)s, %(sum)s)
                        """,
                        {
                            "stid": transaction_id,
                            "account_id": split.account_id,
                            "sum": sum_value,
                        },
                    )

        return await _get_transaction_by_id(conn, transaction_id)

    @delete("/{transaction_id:uuid}", status_code=204)
    async def delete_transaction(
        self,
        conn: psycopg.AsyncConnection,
        transaction_id: UUID,
    ) -> None:
        """Delete a transaction and its splits."""
        # Delete splits first (FK constraint)
        await db.execute(
            conn,
            "DELETE FROM hacc.splits WHERE stid = %(id)s",
            {"id": transaction_id},
        )

        count = await db.execute(
            conn,
            "DELETE FROM hacc.transactions WHERE tid = %(id)s",
            {"id": transaction_id},
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="Transaction not found")
