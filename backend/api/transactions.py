import re
from dataclasses import dataclass
from uuid import UUID

import psycopg
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException
from litestar.params import Parameter

import core.db as db
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse, make_ref


# Regex pattern for dollar amounts: optional $, digits (with optional commas), optional decimal
# Matches: 2500, 2,500, 2500.00, $1,234.56, etc.
AMOUNT_PATTERN = re.compile(r"\$?((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)")


def parse_template_query(query: str) -> tuple[str, float | None]:
    """
    Parse a template search query to extract search terms and optional amount.

    Examples:
        "office depot 125.50" -> ("office depot", 125.50)
        "rent payment" -> ("rent payment", None)
        "$1,234.56 utilities" -> ("utilities", 1234.56)

    Returns:
        Tuple of (search_terms, amount_or_none)
    """
    if not query:
        return "", None

    # Find all amounts in the query
    amounts = AMOUNT_PATTERN.findall(query)

    # Remove amounts from the search string
    search = AMOUNT_PATTERN.sub("", query).strip()
    # Clean up extra whitespace
    search = " ".join(search.split())

    # Use the last amount found (most likely to be the intended amount)
    amount = None
    if amounts:
        # Remove commas and convert to float
        amount_str = amounts[-1].replace(",", "")
        amount = float(amount_str)

    return search, amount


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


def sum_to_debit_credit(sum_value: float) -> tuple[float | None, float | None]:
    """Convert DB sum to API debit/credit."""
    if sum_value > 0:
        return sum_value, None
    elif sum_value < 0:
        return None, abs(sum_value)
    return None, None


def debit_credit_to_sum(debit: float | None, credit: float | None) -> float:
    """Convert API debit/credit to DB sum."""
    if debit:
        return debit
    elif credit:
        return -credit
    return 0.0


@dataclass
class SplitInput:
    account_id: str  # UUID
    debit: float | None = None
    credit: float | None = None


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

    total = 0.0
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

    # Use epsilon for float comparison (0.01 cent tolerance)
    if abs(total) > 0.001:
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

    @get("/template-search")
    async def template_search(
        self,
        conn: psycopg.AsyncConnection,
        q: str = Parameter(default=""),
    ) -> SingleRowResponse:
        """
        Search historical transactions for a template match.

        Query can include optional dollar amount (e.g., "office depot 125.50").
        Returns the best matching transaction template with splits, scaled to
        the specified amount if provided.
        """
        search, amount = parse_template_query(q)

        if not search:
            return SingleRowResponse(columns=[], data=None)

        # Search transactions from last 2 years, score by match quality and frequency
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                """
                WITH candidates AS (
                    SELECT
                        t.tid,
                        t.payee,
                        t.memo,
                        t.trandate,
                        -- Scoring: exact match > prefix > contains
                        CASE
                            WHEN LOWER(t.payee) = LOWER(%(search)s) THEN 100
                            WHEN LOWER(t.payee) LIKE LOWER(%(prefix)s) THEN 80
                            WHEN LOWER(t.payee) LIKE LOWER(%(contains)s) THEN 50
                            ELSE 0
                        END AS payee_score,
                        CASE
                            WHEN LOWER(t.memo) LIKE LOWER(%(contains)s) THEN 30
                            ELSE 0
                        END AS memo_score
                    FROM hacc.transactions t
                    WHERE t.trandate >= CURRENT_DATE - INTERVAL '2 years'
                      AND (
                          t.payee ILIKE %(contains)s
                          OR t.memo ILIKE %(contains)s
                      )
                ),
                grouped AS (
                    SELECT
                        payee,
                        memo,
                        COUNT(*) AS frequency,
                        MAX(trandate) AS last_used,
                        MAX(payee_score) AS payee_score,
                        MAX(memo_score) AS memo_score,
                        -- Get the most recent transaction ID for this pattern
                        (SELECT tid FROM candidates c2
                         WHERE c2.payee IS NOT DISTINCT FROM candidates.payee
                           AND c2.memo IS NOT DISTINCT FROM candidates.memo
                         ORDER BY c2.trandate DESC
                         LIMIT 1) AS latest_tid
                    FROM candidates
                    GROUP BY payee, memo
                ),
                scored AS (
                    SELECT
                        payee,
                        memo,
                        frequency,
                        last_used,
                        latest_tid,
                        -- Total score: match quality + frequency bonus + recency bonus
                        payee_score + memo_score
                            + (LN(frequency + 1) * 15)
                            + (CASE
                                WHEN last_used >= CURRENT_DATE - INTERVAL '30 days' THEN 20
                                WHEN last_used >= CURRENT_DATE - INTERVAL '90 days' THEN 10
                                WHEN last_used >= CURRENT_DATE - INTERVAL '180 days' THEN 5
                                ELSE 0
                            END) AS total_score
                    FROM grouped
                )
                SELECT payee, memo, frequency, latest_tid
                FROM scored
                ORDER BY total_score DESC
                LIMIT 1
                """,
                {
                    "search": search,
                    "prefix": f"{search}%",
                    "contains": f"%{search}%",
                },
            )
            row = await cur.fetchone()

        if not row:
            return SingleRowResponse(columns=[], data=None)

        # Get splits from the most recent matching transaction
        splits = await get_transaction_splits(conn, row["latest_tid"])

        # Scale amounts if a target amount was specified
        if amount is not None and splits:
            # Calculate current total (use absolute sum of all amounts)
            current_total = sum(
                abs(s["debit"] or 0) + abs(s["credit"] or 0) for s in splits
            ) / 2  # Divide by 2 since debits=credits

            if current_total > 0:
                scale_factor = amount / current_total
                for split in splits:
                    if split["debit"] is not None:
                        split["debit"] = round(split["debit"] * scale_factor, 2)
                    if split["credit"] is not None:
                        split["credit"] = round(split["credit"] * scale_factor, 2)

        return SingleRowResponse(
            columns=[],
            data={
                "payee": row["payee"],
                "memo": row["memo"],
                "frequency": row["frequency"],
                "splits": splits,
            },
        )
