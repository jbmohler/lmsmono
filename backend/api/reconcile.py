from dataclasses import dataclass
from uuid import UUID

import psycopg
import psycopg.rows
from litestar import Controller, get, post
from litestar.exceptions import HTTPException, NotFoundException

from core.guards import require_capability


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------


def sql_get_account_info() -> str:
    return """
        SELECT a.acc_name, a.rec_note
        FROM hacc.accounts a
        WHERE a.id = %(account_id)s
    """


def sql_get_prior_balance() -> str:
    """Sum of all splits tagged Bank Reconciled for this account."""
    return """
        SELECT COALESCE(SUM(s.sum), 0) AS prior_balance
        FROM hacc.splits s
        JOIN hacc.tagsplits ts ON ts.split_id = s.sid
        JOIN hacc.tags tg ON tg.id = ts.tag_id
        WHERE s.account_id = %(account_id)s
          AND tg.tag_name = 'Bank Reconciled'
    """


def sql_get_splits() -> str:
    """All splits for this account that are NOT Bank Reconciled, with pending flag."""
    return """
        SELECT
            s.sid AS split_id,
            t.trandate,
            t.tranref,
            t.payee,
            t.memo,
            s.sum,
            EXISTS (
                SELECT 1
                FROM hacc.tagsplits ts2
                JOIN hacc.tags tg2 ON tg2.id = ts2.tag_id
                WHERE ts2.split_id = s.sid
                  AND tg2.tag_name = 'Bank Pending'
            ) AS is_pending
        FROM hacc.splits s
        JOIN hacc.transactions t ON t.tid = s.stid
        WHERE s.account_id = %(account_id)s
          AND NOT EXISTS (
              SELECT 1
              FROM hacc.tagsplits ts
              JOIN hacc.tags tg ON tg.id = ts.tag_id
              WHERE ts.split_id = s.sid
                AND tg.tag_name = 'Bank Reconciled'
          )
        ORDER BY t.trandate ASC, t.tid ASC
    """


def sql_get_tag_id() -> str:
    return "SELECT id FROM hacc.tags WHERE tag_name = %(tag_name)s"


def sql_check_split_eligible() -> str:
    """Verify split belongs to account and is not already Bank Reconciled."""
    return """
        SELECT s.sid
        FROM hacc.splits s
        WHERE s.sid = %(split_id)s
          AND s.account_id = %(account_id)s
          AND NOT EXISTS (
              SELECT 1
              FROM hacc.tagsplits ts
              JOIN hacc.tags tg ON tg.id = ts.tag_id
              WHERE ts.split_id = s.sid
                AND tg.tag_name = 'Bank Reconciled'
          )
    """


def sql_check_tagsplit_exists() -> str:
    return """
        SELECT 1 FROM hacc.tagsplits
        WHERE tag_id = %(tag_id)s AND split_id = %(split_id)s
    """


def sql_insert_tagsplit() -> str:
    return """
        INSERT INTO hacc.tagsplits (tag_id, split_id)
        VALUES (%(tag_id)s, %(split_id)s)
        ON CONFLICT DO NOTHING
    """


def sql_delete_tagsplit() -> str:
    return """
        DELETE FROM hacc.tagsplits
        WHERE tag_id = %(tag_id)s AND split_id = %(split_id)s
    """


def sql_get_pending_splits_for_account() -> str:
    return """
        SELECT s.sid
        FROM hacc.splits s
        JOIN hacc.tagsplits ts ON ts.split_id = s.sid
        WHERE s.account_id = %(account_id)s
          AND ts.tag_id = %(pending_tag_id)s
    """


def sql_remove_pending_from_account() -> str:
    """Remove Bank Pending from all splits in this account."""
    return """
        DELETE FROM hacc.tagsplits ts
        WHERE ts.tag_id = %(pending_tag_id)s
          AND ts.split_id IN (
              SELECT s.sid FROM hacc.splits s
              WHERE s.account_id = %(account_id)s
          )
    """


# ---------------------------------------------------------------------------
# Response dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ReconcileSplit:
    split_id: str
    trandate: str
    tranref: str | None
    payee: str | None
    memo: str | None
    debit: float | None
    credit: float | None
    is_pending: bool


@dataclass
class ReconcileData:
    account_id: str
    acc_name: str
    rec_note: str | None
    prior_reconciled_balance: float
    splits: list[ReconcileSplit]


@dataclass
class ToggleResult:
    split_id: str
    is_pending: bool


@dataclass
class FinalizeResult:
    reconciled_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sum_to_debit_credit(sum_value: float | None) -> tuple[float | None, float | None]:
    if sum_value is None:
        return None, None
    if sum_value > 0:
        return float(sum_value), None
    if sum_value < 0:
        return None, float(abs(sum_value))
    return None, None


async def _get_tag_id(conn: psycopg.AsyncConnection, tag_name: str) -> UUID:
    async with conn.cursor() as cur:
        await cur.execute(sql_get_tag_id(), {"tag_name": tag_name})
        row = await cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=500,
                detail=f"Tag '{tag_name}' not found. Run seed data to create reconciliation tags.",
            )
        return row[0]


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class ReconcileController(Controller):
    path = "/api/reconcile"
    tags = ["reconcile"]

    @get("/{account_id:uuid}", guards=[require_capability("accounts:read")])
    async def get_reconcile_data(
        self,
        conn: psycopg.AsyncConnection,
        account_id: UUID,
    ) -> ReconcileData:
        """Return account info, prior reconciled balance, and unreconciled splits."""
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql_get_account_info(), {"account_id": account_id})
            account_row = await cur.fetchone()
            if not account_row:
                raise NotFoundException(detail="Account not found")

            await cur.execute(sql_get_prior_balance(), {"account_id": account_id})
            balance_row = await cur.fetchone()
            prior_balance = float(balance_row["prior_balance"]) if balance_row else 0.0

            await cur.execute(sql_get_splits(), {"account_id": account_id})
            split_rows = await cur.fetchall()

        splits = []
        for row in split_rows:
            debit, credit = _sum_to_debit_credit(row["sum"])
            splits.append(ReconcileSplit(
                split_id=str(row["split_id"]),
                trandate=row["trandate"].isoformat(),
                tranref=row["tranref"],
                payee=row["payee"],
                memo=row["memo"],
                debit=debit,
                credit=credit,
                is_pending=row["is_pending"],
            ))

        return ReconcileData(
            account_id=str(account_id),
            acc_name=account_row["acc_name"],
            rec_note=account_row["rec_note"],
            prior_reconciled_balance=prior_balance,
            splits=splits,
        )

    @post(
        "/{account_id:uuid}/splits/{split_id:uuid}/toggle",
        guards=[require_capability("accounts:write")],
    )
    async def toggle_split_pending(
        self,
        conn: psycopg.AsyncConnection,
        account_id: UUID,
        split_id: UUID,
    ) -> ToggleResult:
        """Toggle Bank Pending tag on a split. Saves immediately to DB."""
        pending_tag_id = await _get_tag_id(conn, "Bank Pending")

        async with conn.cursor() as cur:
            # Verify split belongs to this account and isn't Bank Reconciled
            await cur.execute(
                sql_check_split_eligible(),
                {"split_id": split_id, "account_id": account_id},
            )
            if not await cur.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail="Split not found, not in this account, or already reconciled",
                )

            # Check current pending state
            await cur.execute(
                sql_check_tagsplit_exists(),
                {"tag_id": pending_tag_id, "split_id": split_id},
            )
            currently_pending = await cur.fetchone() is not None

            if currently_pending:
                await cur.execute(
                    sql_delete_tagsplit(),
                    {"tag_id": pending_tag_id, "split_id": split_id},
                )
                return ToggleResult(split_id=str(split_id), is_pending=False)
            else:
                await cur.execute(
                    sql_insert_tagsplit(),
                    {"tag_id": pending_tag_id, "split_id": split_id},
                )
                return ToggleResult(split_id=str(split_id), is_pending=True)

    @post(
        "/{account_id:uuid}/finalize",
        guards=[require_capability("accounts:write")],
    )
    async def finalize_reconciliation(
        self,
        conn: psycopg.AsyncConnection,
        account_id: UUID,
    ) -> FinalizeResult:
        """Promote all Bank Pending splits for this account to Bank Reconciled."""
        pending_tag_id = await _get_tag_id(conn, "Bank Pending")
        reconciled_tag_id = await _get_tag_id(conn, "Bank Reconciled")

        async with conn.cursor() as cur:
            # Find all pending splits for this account
            await cur.execute(
                sql_get_pending_splits_for_account(),
                {"account_id": account_id, "pending_tag_id": pending_tag_id},
            )
            rows = await cur.fetchall()
            split_ids = [row[0] for row in rows]

            if not split_ids:
                return FinalizeResult(reconciled_count=0)

            # Add Bank Reconciled to each pending split
            for sid in split_ids:
                await cur.execute(
                    sql_insert_tagsplit(),
                    {"tag_id": reconciled_tag_id, "split_id": sid},
                )

            # Remove all Bank Pending for this account
            await cur.execute(
                sql_remove_pending_from_account(),
                {"pending_tag_id": pending_tag_id, "account_id": account_id},
            )

        return FinalizeResult(reconciled_count=len(split_ids))
