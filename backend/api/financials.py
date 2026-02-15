import datetime

import psycopg
import psycopg.rows
from litestar import Controller, get
from litestar.params import Parameter

from core.guards import require_capability
from core.responses import ColumnMeta, MultiRowResponse


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------


def sql_balance_sheet_at_date() -> str:
    """Balance sheet at a given date, rolling P&L into retained earnings."""
    return """
        WITH balances AS (
            SELECT
                accounts.id,
                accounts.type_id,
                accounts.retearn_id,
                SUM(splits.sum) AS debit
            FROM hacc.accounts
            JOIN hacc.splits ON splits.account_id = accounts.id
            JOIN hacc.transactions ON transactions.tid = splits.stid
            WHERE transactions.trandate <= %(d)s
            GROUP BY accounts.id, accounts.type_id, accounts.retearn_id
        ), balsheet AS (
            SELECT
                CASE WHEN accounttypes.balance_sheet
                    THEN balances.id
                    ELSE ret.id
                END AS account_id,
                balances.debit
            FROM balances
            JOIN hacc.accounttypes ON accounttypes.id = balances.type_id
            LEFT OUTER JOIN hacc.accounts ret ON ret.id = balances.retearn_id
        )
        SELECT
            accounttypes.id AS atype_id,
            accounttypes.atype_name,
            accounttypes.sort AS atype_sort,
            accounttypes.debit AS debit_account,
            journals.id AS jrn_id,
            journals.jrn_name,
            accounts.id,
            accounts.acc_name,
            accounts.description,
            balsheet.debit
        FROM (
            SELECT balsheet.account_id, SUM(balsheet.debit) AS debit
            FROM balsheet
            GROUP BY balsheet.account_id
            HAVING SUM(balsheet.debit) <> 0.
        ) balsheet
        JOIN hacc.accounts ON accounts.id = balsheet.account_id
        JOIN hacc.accounttypes ON accounttypes.id = accounts.type_id
        JOIN hacc.journals ON journals.id = accounts.journal_id
    """


def sql_current_balance_accounts() -> str:
    """Balance sheet accounts with non-zero balances or recent activity."""
    return """
        WITH balance AS (
            """ + sql_balance_sheet_at_date() + """
        ), recent AS (
            SELECT DISTINCT accounts.id
            FROM hacc.accounts
            JOIN hacc.splits ON splits.account_id = accounts.id
            JOIN hacc.transactions ON transactions.tid = splits.stid
            WHERE transactions.trandate
                BETWEEN %(d)s - INTERVAL '30 days'
                AND %(d)s + INTERVAL '30 days'
        )
        SELECT
            accounttypes.id AS atype_id,
            accounttypes.atype_name,
            accounttypes.sort AS atype_sort,
            accounttypes.debit AS debit_account,
            journals.id AS jrn_id,
            journals.jrn_name,
            accounts.id,
            accounts.acc_name,
            accounts.description,
            balance.debit
        FROM hacc.accounts
        LEFT OUTER JOIN hacc.journals ON journals.id = accounts.journal_id
        LEFT OUTER JOIN hacc.accounttypes ON accounttypes.id = accounts.type_id
        LEFT OUTER JOIN balance ON balance.id = accounts.id
        WHERE accounts.id IN (
            (SELECT id FROM balance)
            UNION
            (SELECT id FROM recent)
        )
        AND accounttypes.balance_sheet
        ORDER BY accounttypes.sort, journals.jrn_name, accounts.acc_name
    """


def sql_profit_and_loss() -> str:
    """Profit & loss for a date range (non-balance-sheet accounts)."""
    return """
        WITH deltas AS (
            SELECT
                accounts.id AS account_id,
                SUM(splits.sum) AS debit
            FROM hacc.transactions
            JOIN hacc.splits ON transactions.tid = splits.stid
            JOIN hacc.accounts ON splits.account_id = accounts.id
            JOIN hacc.accounttypes ON accounttypes.id = accounts.type_id
            WHERE transactions.trandate BETWEEN %(d1)s AND %(d2)s
                AND NOT accounttypes.balance_sheet
            GROUP BY accounts.id, accounts.type_id
            HAVING SUM(splits.sum) <> 0
        )
        SELECT
            accounttypes.id AS atype_id,
            accounttypes.atype_name,
            accounttypes.sort AS atype_sort,
            accounttypes.debit AS debit_account,
            journals.id AS jrn_id,
            journals.jrn_name,
            accounts.id,
            accounts.acc_name,
            accounts.description,
            deltas.debit
        FROM deltas
        JOIN hacc.accounts ON accounts.id = deltas.account_id
        JOIN hacc.accounttypes ON accounttypes.id = accounts.type_id
        JOIN hacc.journals ON journals.id = accounts.journal_id
        ORDER BY accounttypes.sort, journals.jrn_name
    """


CURRENT_BALANCE_COLUMNS = [
    ColumnMeta(key="atype_id", label="Type ID", type="uuid"),
    ColumnMeta(key="atype_name", label="Account Type", type="string"),
    ColumnMeta(key="atype_sort", label="Type Sort", type="number"),
    ColumnMeta(key="debit_account", label="Debit Account", type="boolean"),
    ColumnMeta(key="journal", label="Journal", type="ref"),
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="acc_name", label="Account", type="string"),
    ColumnMeta(key="description", label="Description", type="string"),
    ColumnMeta(key="balance", label="Balance", type="currency"),
]


def transform_balance_row(row: dict) -> dict:
    """Transform a balance sheet row, sign-adjusting for credit accounts."""
    raw_debit = row["debit"] or 0.0
    balance = raw_debit if row["debit_account"] else -raw_debit
    return {
        "atype_id": row["atype_id"],
        "atype_name": row["atype_name"],
        "atype_sort": row["atype_sort"],
        "debit_account": row["debit_account"],
        "journal": {"id": str(row["jrn_id"]), "name": row["jrn_name"]},
        "id": row["id"],
        "acc_name": row["acc_name"],
        "description": row["description"],
        "balance": balance,
    }


PROFIT_LOSS_COLUMNS = [
    ColumnMeta(key="atype_id", label="Type ID", type="uuid"),
    ColumnMeta(key="atype_name", label="Account Type", type="string"),
    ColumnMeta(key="atype_sort", label="Type Sort", type="number"),
    ColumnMeta(key="debit_account", label="Debit Account", type="boolean"),
    ColumnMeta(key="journal", label="Journal", type="ref"),
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="acc_name", label="Account", type="string"),
    ColumnMeta(key="description", label="Description", type="string"),
    ColumnMeta(key="amount", label="Amount", type="currency"),
]


def transform_pnl_row(row: dict) -> dict:
    """Transform a P&L row, sign-adjusting for credit accounts."""
    raw_debit = row["debit"] or 0.0
    amount = raw_debit if row["debit_account"] else -raw_debit
    return {
        "atype_id": row["atype_id"],
        "atype_name": row["atype_name"],
        "atype_sort": row["atype_sort"],
        "debit_account": row["debit_account"],
        "journal": {"id": str(row["jrn_id"]), "name": row["jrn_name"]},
        "id": row["id"],
        "acc_name": row["acc_name"],
        "description": row["description"],
        "amount": amount,
    }


class FinancialsController(Controller):
    path = "/api/reports"
    tags = ["reports"]

    @get(
        "/current-balance-accounts",
        guards=[require_capability("transactions:read")],
    )
    async def current_balance_accounts(
        self,
        conn: psycopg.AsyncConnection,
        d: str = Parameter(
            default=None,
            description="Report date (ISO 8601). Defaults to today.",
        ),
    ) -> MultiRowResponse:
        """Balance sheet accounts with non-zero balances or recent activity."""
        if d is None:
            d = datetime.date.today().isoformat()
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql_current_balance_accounts(), {"d": d})
            rows = await cur.fetchall()
            data = [transform_balance_row(dict(row)) for row in rows]
            return MultiRowResponse(
                columns=CURRENT_BALANCE_COLUMNS, data=data
            )

    @get(
        "/profit-loss",
        guards=[require_capability("transactions:read")],
    )
    async def profit_and_loss(
        self,
        conn: psycopg.AsyncConnection,
        d1: str = Parameter(
            default=None,
            description="Start date (ISO 8601). Defaults to start of current year.",
        ),
        d2: str = Parameter(
            default=None,
            description="End date (ISO 8601). Defaults to today.",
        ),
    ) -> MultiRowResponse:
        """Profit & loss statement for a date range."""
        today = datetime.date.today()
        if d1 is None:
            d1 = today.replace(month=1, day=1).isoformat()
        if d2 is None:
            d2 = today.isoformat()
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql_profit_and_loss(), {"d1": d1, "d2": d2})
            rows = await cur.fetchall()
            data = [transform_pnl_row(dict(row)) for row in rows]
            return MultiRowResponse(
                columns=PROFIT_LOSS_COLUMNS, data=data
            )
