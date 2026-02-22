import calendar
import datetime
from typing import Any

import psycopg
import psycopg.rows
from litestar import Controller, get
from litestar.exceptions import HTTPException, NotFoundException
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


def _balance_sheet_ctes(idx: int, param: str) -> str:
    """Generate the three CTEs for one period of a multi-period balance sheet.

    Returns CTEs named balances_{idx}, balsheet_{idx}, bs_{idx} that compute
    the balance sheet as-of the parameter named `param`.
    """
    return f"""
        balances_{idx} AS (
            SELECT
                accounts.id,
                accounts.type_id,
                accounts.retearn_id,
                SUM(splits.sum) AS debit
            FROM hacc.accounts
            JOIN hacc.splits ON splits.account_id = accounts.id
            JOIN hacc.transactions ON transactions.tid = splits.stid
            WHERE transactions.trandate <= %({param})s
            GROUP BY accounts.id, accounts.type_id, accounts.retearn_id
        ), balsheet_{idx} AS (
            SELECT
                CASE WHEN accounttypes.balance_sheet
                    THEN balances_{idx}.id
                    ELSE ret.id
                END AS account_id,
                balances_{idx}.debit
            FROM balances_{idx}
            JOIN hacc.accounttypes ON accounttypes.id = balances_{idx}.type_id
            LEFT OUTER JOIN hacc.accounts ret ON ret.id = balances_{idx}.retearn_id
        ), bs_{idx} AS (
            SELECT balsheet_{idx}.account_id, SUM(balsheet_{idx}.debit) AS debit
            FROM balsheet_{idx}
            GROUP BY balsheet_{idx}.account_id
            HAVING SUM(balsheet_{idx}.debit) <> 0.
        )"""


def sql_multi_period_balance_sheet(n: int) -> str:
    """Build a single query that computes balance sheets for n periods.

    Parameters are named d_0, d_1, ..., d_{n-1}.
    Returns one row per account that appears in any period, with columns
    bal_0, bal_1, ..., bal_{n-1} for each period's balance.
    """
    # Build the CTE chain
    cte_parts = []
    for i in range(n):
        cte_parts.append(_balance_sheet_ctes(i, f"d_{i}"))

    # Union all account IDs across periods
    union_parts = [f"SELECT account_id FROM bs_{i}" for i in range(n)]
    all_accounts = "all_accounts AS (\n" + "\n            UNION\n".join(
        f"            {p}" for p in union_parts
    ) + "\n        )"
    cte_parts.append(all_accounts)

    # Build the SELECT with one COALESCE column per period
    bal_cols = ",\n            ".join(
        f"COALESCE(bs_{i}.debit, 0) AS bal_{i}" for i in range(n)
    )

    # Build the LEFT JOINs
    joins = "\n        ".join(
        f"LEFT JOIN bs_{i} ON bs_{i}.account_id = aa.account_id"
        for i in range(n)
    )

    return f"""
        WITH {", ".join(cte_parts)}
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
            {bal_cols}
        FROM all_accounts aa
        JOIN hacc.accounts ON accounts.id = aa.account_id
        JOIN hacc.accounttypes ON accounttypes.id = accounts.type_id
        JOIN hacc.journals ON journals.id = accounts.journal_id
        {joins}
        ORDER BY accounttypes.sort, journals.jrn_name, accounts.acc_name
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


def sql_profit_loss_transactions() -> str:
    """Individual splits for non-balance-sheet accounts within a date range."""
    return """
        SELECT
            accounttypes.id AS atype_id,
            accounttypes.atype_name,
            accounttypes.sort AS atype_sort,
            accounttypes.debit AS debit_account,
            accounts.id AS account_id,
            accounts.acc_name,
            journals.id AS jrn_id,
            journals.jrn_name,
            transactions.tid AS id,
            transactions.trandate,
            transactions.payee,
            transactions.memo,
            splits.sum
        FROM hacc.transactions
        JOIN hacc.splits ON transactions.tid = splits.stid
        JOIN hacc.accounts ON splits.account_id = accounts.id
        JOIN hacc.accounttypes ON accounttypes.id = accounts.type_id
        JOIN hacc.journals ON journals.id = accounts.journal_id
        WHERE transactions.trandate BETWEEN %(d1)s AND %(d2)s
            AND NOT accounttypes.balance_sheet
        ORDER BY accounttypes.sort, transactions.trandate, accounts.acc_name
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


PL_TRANSACTION_COLUMNS = [
    ColumnMeta(key="atype_id", label="Type ID", type="uuid"),
    ColumnMeta(key="atype_name", label="Account Type", type="string"),
    ColumnMeta(key="atype_sort", label="Type Sort", type="number"),
    ColumnMeta(key="debit_account", label="Debit Account", type="boolean"),
    ColumnMeta(key="account_id", label="Account ID", type="uuid"),
    ColumnMeta(key="acc_name", label="Account", type="string"),
    ColumnMeta(key="journal", label="Journal", type="ref"),
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="trandate", label="Date", type="date"),
    ColumnMeta(key="payee", label="Payee", type="string"),
    ColumnMeta(key="memo", label="Memo", type="string"),
    ColumnMeta(key="amount", label="Amount", type="currency"),
]


def transform_pl_txn_row(row: dict) -> dict:
    """Transform a P&L transaction row, sign-adjusting for credit accounts."""
    raw = row["sum"] or 0.0
    amount = raw if row["debit_account"] else -raw
    return {
        "atype_id": row["atype_id"],
        "atype_name": row["atype_name"],
        "atype_sort": row["atype_sort"],
        "debit_account": row["debit_account"],
        "account_id": row["account_id"],
        "acc_name": row["acc_name"],
        "journal": {"id": str(row["jrn_id"]), "name": row["jrn_name"]},
        "id": row["id"],
        "trandate": row["trandate"].isoformat()
        if hasattr(row["trandate"], "isoformat")
        else row["trandate"],
        "payee": row["payee"],
        "memo": row["memo"],
        "amount": amount,
    }


def sql_account_running_balance() -> str:
    """Ledger-style running balance for a single balance sheet account with speculative future rows."""
    return """
        WITH
        balances AS (
            SELECT COALESCE(SUM(splits.sum), 0) AS debit
            FROM hacc.splits
            JOIN hacc.transactions ON transactions.tid = splits.stid
            WHERE splits.account_id = %(account_id)s
              AND transactions.trandate <= %(d)s
        ),
        recent_txns AS (
            SELECT transactions.trandate, transactions.payee, transactions.memo, splits.sum AS amount
            FROM hacc.splits
            JOIN hacc.transactions ON transactions.tid = splits.stid
            WHERE splits.account_id = %(account_id)s
              AND transactions.trandate >= CURRENT_DATE - INTERVAL '12 months'
        ),
        recurrence_groups AS (
            SELECT
                payee, memo,
                COUNT(*) AS occurrence_count,
                MAX(trandate) AS last_date,
                AVG(amount) AS avg_amount,
                CASE WHEN COUNT(*) > 1
                    THEN (MAX(trandate) - MIN(trandate))::FLOAT / (COUNT(*) - 1)
                    ELSE NULL
                END AS avg_days_between
            FROM recent_txns
            GROUP BY payee, memo
            HAVING COUNT(*) >= 2
        ),
        speculative AS (
            SELECT
                NULL::UUID AS tid,
                (rg.last_date + (rg.avg_days_between * g.n)::INTEGER)::DATE AS trandate,
                NULL::TEXT AS reference,
                rg.payee, rg.memo,
                rg.avg_amount AS amount,
                TRUE AS is_speculative
            FROM recurrence_groups rg
            CROSS JOIN generate_series(1, 30) AS g(n)
            WHERE rg.avg_days_between IS NOT NULL
              AND (rg.last_date + (rg.avg_days_between * g.n)::INTEGER)::DATE
                  BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '3 weeks'
        ),
        all_rows AS (
            SELECT NULL::UUID AS tid, %(d)s::DATE AS trandate, NULL::TEXT AS reference,
                   'Initial Balance'::TEXT AS payee, NULL::TEXT AS memo,
                   NULL::NUMERIC(12,2) AS amount, FALSE AS is_speculative
            UNION ALL
            SELECT transactions.tid, transactions.trandate, transactions.tranref AS reference,
                   transactions.payee, transactions.memo, splits.sum AS amount, FALSE AS is_speculative
            FROM hacc.splits
            JOIN hacc.transactions ON transactions.tid = splits.stid
            WHERE splits.account_id = %(account_id)s
              AND transactions.trandate > %(d)s
            UNION ALL
            SELECT tid, trandate, reference, payee, memo, amount, is_speculative
            FROM speculative
        )
        SELECT
            tid, trandate, reference, payee, memo, amount, is_speculative,
            (SELECT debit FROM balances) + COALESCE(SUM(amount) OVER (ORDER BY trandate, amount), 0) AS balance
        FROM all_rows
        ORDER BY trandate, amount
    """


ACCOUNT_RUNNING_BALANCE_COLUMNS = [
    ColumnMeta(key="tid", label="Transaction ID", type="uuid"),
    ColumnMeta(key="trandate", label="Date", type="date"),
    ColumnMeta(key="reference", label="Reference", type="string"),
    ColumnMeta(key="payee", label="Payee", type="string"),
    ColumnMeta(key="memo", label="Memo", type="string"),
    ColumnMeta(key="amount", label="Amount", type="currency"),
    ColumnMeta(key="balance", label="Balance", type="currency"),
    ColumnMeta(key="is_speculative", label="Speculative", type="boolean"),
]


def transform_arb_row(row: dict, debit_account: bool) -> dict:
    """Transform an account running balance row, sign-adjusting for credit accounts."""
    sign = 1 if debit_account else -1
    raw_amount = row["amount"]
    raw_balance = row["balance"]
    return {
        "tid": str(row["tid"]) if row["tid"] else None,
        "trandate": row["trandate"].isoformat() if hasattr(row["trandate"], "isoformat") else row["trandate"],
        "reference": row["reference"],
        "payee": row["payee"],
        "memo": row["memo"],
        "amount": float(raw_amount * sign) if raw_amount is not None else None,
        "balance": float(raw_balance * sign) if raw_balance is not None else None,
        "is_speculative": row["is_speculative"],
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
        "/multi-period-balance-sheet",
        guards=[require_capability("transactions:read")],
    )
    async def multi_period_balance_sheet(
        self,
        conn: psycopg.AsyncConnection,
        year: int = Parameter(description="Report year."),
        month: int = Parameter(description="Report month (1-12)."),
        periods: int = Parameter(description="Number of annual periods."),
    ) -> dict[str, Any]:
        """Balance sheet across multiple same-month annual periods."""
        # Compute the last day of the target month for each year
        dates: list[str] = []
        for i in range(periods):
            y = year - i
            last_day = calendar.monthrange(y, month)[1]
            dates.append(datetime.date(y, month, last_day).isoformat())

        n = len(dates)
        params = {f"d_{i}": dates[i] for i in range(n)}

        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql_multi_period_balance_sheet(n), params)
            rows = await cur.fetchall()

        data = []
        for row in rows:
            is_debit = row["debit_account"]
            balances = []
            for i in range(n):
                raw = row[f"bal_{i}"] or 0.0
                balances.append(raw if is_debit else -raw)
            data.append({
                "atype_id": row["atype_id"],
                "atype_name": row["atype_name"],
                "atype_sort": row["atype_sort"],
                "debit_account": is_debit,
                "journal": {"id": str(row["jrn_id"]), "name": row["jrn_name"]},
                "id": row["id"],
                "acc_name": row["acc_name"],
                "description": row["description"],
                "balances": balances,
            })

        return {"periods": dates, "data": data}

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

    @get(
        "/profit-loss-transactions",
        guards=[require_capability("transactions:read")],
    )
    async def profit_loss_transactions(
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
        """P&L transaction detail for a date range."""
        today = datetime.date.today()
        if d1 is None:
            d1 = today.replace(month=1, day=1).isoformat()
        if d2 is None:
            d2 = today.isoformat()
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                sql_profit_loss_transactions(), {"d1": d1, "d2": d2}
            )
            rows = await cur.fetchall()
            data = [transform_pl_txn_row(dict(row)) for row in rows]
            return MultiRowResponse(
                columns=PL_TRANSACTION_COLUMNS, data=data
            )

    @get("/account-running-balance", guards=[require_capability("transactions:read")])
    async def account_running_balance(
        self,
        conn: psycopg.AsyncConnection,
        account_id: str = Parameter(description="Account UUID"),
        d: str = Parameter(
            default=None,
            description="Start date (ISO 8601). Defaults to start of current year.",
        ),
    ) -> MultiRowResponse:
        """Ledger-style running balance for a single balance sheet account."""
        today = datetime.date.today()
        if d is None:
            d = today.replace(month=1, day=1).isoformat()
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                "SELECT accounttypes.balance_sheet, accounttypes.debit AS debit_account "
                "FROM hacc.accounts "
                "JOIN hacc.accounttypes ON accounttypes.id = accounts.type_id "
                "WHERE accounts.id = %(account_id)s",
                {"account_id": account_id},
            )
            meta = await cur.fetchone()
        if meta is None:
            raise NotFoundException(detail="Account not found")
        if not meta["balance_sheet"]:
            raise HTTPException(status_code=400, detail="Account is not a balance sheet account")
        debit_account = meta["debit_account"]
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql_account_running_balance(), {"account_id": account_id, "d": d})
            rows = await cur.fetchall()
        data = [transform_arb_row(dict(row), debit_account) for row in rows]
        return MultiRowResponse(columns=ACCOUNT_RUNNING_BALANCE_COLUMNS, data=data)
