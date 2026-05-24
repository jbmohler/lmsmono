#!/usr/bin/env python3
"""LMS command-line client."""

import argparse
import datetime
import getpass
import json
import os
import sys

import httpx
from xlsx import FILL_ASSETS, FILL_LIAB, FILL_SUBTOTAL, ReportSheet

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".lms")
SESSION_FILE = os.path.join(CONFIG_DIR, "session")
DEFAULT_BASE_URL = "http://localhost:8080"


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def load_session() -> dict:
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE) as f:
                return json.loads(f.read())
        except Exception:
            return {}
    return {}


def save_session(data: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        f.write(json.dumps(data))
    os.chmod(SESSION_FILE, 0o600)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _do_login(base_url: str) -> str:
    """Prompt for credentials, POST to login, return session_id."""
    print("Authentication required.")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    with httpx.Client(base_url=base_url) as client:
        resp = client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )

    if resp.status_code not in (200, 201):
        try:
            detail = resp.json().get("detail", "Login failed")
        except Exception:
            detail = f"HTTP {resp.status_code}"
        print(f"Error: {detail}", file=sys.stderr)
        sys.exit(1)

    session_id = resp.cookies.get("session_id")
    if not session_id:
        print("Error: No session cookie in response", file=sys.stderr)
        sys.exit(1)

    return session_id


def ensure_auth(base_url: str | None) -> httpx.Client:
    """Return an authenticated HTTP client, logging in if necessary.

    Checks the saved session first; re-authenticates on 401.
    """
    session = load_session()
    effective_url = base_url or session.get("base_url") or DEFAULT_BASE_URL

    if session.get("session_id"):
        client = httpx.Client(
            base_url=effective_url,
            cookies={"session_id": session["session_id"]},
        )
        resp = client.get("/api/auth/me")
        if resp.status_code == 200:
            return client
        client.close()

    session_id = _do_login(effective_url)
    save_session({"session_id": session_id, "base_url": effective_url})
    print("Logged in.")
    return httpx.Client(
        base_url=effective_url,
        cookies={"session_id": session_id},
    )


# ---------------------------------------------------------------------------
# Balance sheet export
# ---------------------------------------------------------------------------


def cmd_balance_sheet(args: argparse.Namespace) -> None:
    today = datetime.date.today()
    prior_month_end = today.replace(day=1) - datetime.timedelta(days=1)
    year: int = args.year or prior_month_end.year
    month: int = args.month or prior_month_end.month
    periods: int = args.periods

    client = ensure_auth(args.url)
    resp = client.get(
        "/api/reports/multi-period-balance-sheet",
        params={"year": year, "month": month, "periods": periods},
    )
    client.close()

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception:
            detail = f"HTTP {resp.status_code}"
        print(f"Error: {detail}", file=sys.stderr)
        sys.exit(1)

    payload = resp.json()
    period_dates: list[str] = payload["periods"]
    rows: list[dict] = payload["data"]

    output: str = args.output or f"balance_sheet_{year}_{month:02d}.xlsx"
    _write_balance_sheet_xlsx(output, period_dates, rows)
    print(f"Written: {output}")


def _write_balance_sheet_xlsx(
    path: str,
    period_dates: list[str],
    rows: list[dict],
) -> None:
    n = len(period_dates)
    rs = ReportSheet("Balance Sheet", n_text=3, n_val=n)
    rs.write_title("Balance Sheet")
    rs.write_generated()
    rs.write_blank()
    rs.write_headers(["Journal", "Account", "Account Name"], period_dates)
    rs.set_col_widths([20, 24, 32] + [16] * n)

    current_atype: str | None = None
    current_is_debit: bool = True
    section_data_start: int = rs.row
    asset_subtotal_rows: list[int] = []
    liab_subtotal_rows: list[int] = []
    total_assets_written = False

    def flush_section() -> None:
        if current_atype is None:
            return
        subtotal = rs.write_subtotal_row(f"Total {current_atype}", section_data_start)
        if current_is_debit:
            asset_subtotal_rows.append(subtotal)
        else:
            liab_subtotal_rows.append(subtotal)
        rs.write_blank()

    for data_row in rows:
        atype = data_row["atype_name"]
        is_debit: bool = data_row["debit_account"]

        if atype != current_atype:
            flush_section()
            if current_atype is not None and current_is_debit and not is_debit:
                rs.write_ref_row("Total Assets", asset_subtotal_rows, FILL_ASSETS)
                rs.write_blank()
                total_assets_written = True
            current_atype = atype
            current_is_debit = is_debit
            rs.write_section_header(atype)
            section_data_start = rs.row

        rs.write_data_row(
            [data_row["journal"]["name"], data_row["acc_name"], data_row.get("description") or ""],
            [float(bal or 0.0) for bal in data_row["balances"]],
        )

    flush_section()

    if not total_assets_written:
        rs.write_ref_row("Total Assets", asset_subtotal_rows, FILL_ASSETS)
        rs.write_blank()

    rs.write_ref_row("Total Liabilities + Equity", liab_subtotal_rows, FILL_LIAB)
    rs.save(path)


# ---------------------------------------------------------------------------
# Profit & loss export
# ---------------------------------------------------------------------------


def _rolling_half_periods(anchor_year: int, anchor_month: int, n_periods: int) -> list[tuple[str, str, str]]:
    """Return (label, d1, d2) tuples for n_periods rolling 6-month windows.

    Each window ends on the last day of the anchor month and steps back 6
    months at a time.  label is the end month formatted as 'Mon YYYY'.
    """
    import calendar

    end_year, end_month = anchor_year, anchor_month
    periods: list[tuple[str, str, str]] = []

    for _ in range(n_periods):
        last_day = calendar.monthrange(end_year, end_month)[1]
        d2 = datetime.date(end_year, end_month, last_day)

        start_month = end_month - 5
        start_year = end_year
        if start_month <= 0:
            start_month += 12
            start_year -= 1
        d1 = datetime.date(start_year, start_month, 1)

        label = d2.strftime("%b %Y")
        periods.append((label, d1.isoformat(), d2.isoformat()))

        # Step end back 6 months
        end_month -= 6
        if end_month <= 0:
            end_month += 12
            end_year -= 1

    return periods


def cmd_profit_loss(args: argparse.Namespace) -> None:
    today = datetime.date.today()
    prior_month_end = today.replace(day=1) - datetime.timedelta(days=1)
    year: int = args.year or prior_month_end.year
    month: int = args.month or prior_month_end.month
    n_years: int = args.years

    periods = _rolling_half_periods(year, month, n_years * 2)

    client = ensure_auth(args.url)
    period_data: list[tuple[str, list[dict]]] = []
    for label, d1, d2 in periods:
        resp = client.get("/api/reports/profit-loss", params={"d1": d1, "d2": d2})
        if resp.status_code != 200:
            client.close()
            try:
                detail = resp.json().get("detail", f"HTTP {resp.status_code}")
            except Exception:
                detail = f"HTTP {resp.status_code}"
            print(f"Error fetching {label}: {detail}", file=sys.stderr)
            sys.exit(1)
        period_data.append((label, resp.json()["data"]))
    client.close()

    output: str = args.output or f"profit_loss_{year}_{month:02d}.xlsx"
    _write_profit_loss_xlsx(output, periods, period_data)
    print(f"Written: {output}")


def _write_profit_loss_xlsx(
    path: str,
    periods: list[tuple[str, str, str]],
    period_data: list[tuple[str, list[dict]]],
) -> None:
    # Build a combined account list with one amount per period
    # period_data[i] = (label, rows) where each row has acc_name, atype_name, journal, amount
    labels = [p[0] for p in periods]
    n = len(labels)

    # Index amounts by account id per period
    account_meta: dict[str, dict] = {}  # id -> {atype, journal, acc_name, description}
    amounts: dict[str, list[float]] = {}  # id -> [amount_per_period]

    for i, (_, rows) in enumerate(period_data):
        for row in rows:
            aid = row["id"]
            if aid not in account_meta:
                account_meta[aid] = {
                    "atype_name": row["atype_name"],
                    "atype_sort": row["atype_sort"],
                    "debit_account": row["debit_account"],
                    "journal": row["journal"],
                    "acc_name": row["acc_name"],
                    "description": row.get("description") or "",
                }
                amounts[aid] = [0.0] * n
            amounts[aid][i] = float(row.get("amount") or 0.0)

    # Sort accounts by atype_sort, journal name, acc_name
    ordered = sorted(
        account_meta.keys(),
        key=lambda aid: (
            account_meta[aid]["atype_sort"],
            account_meta[aid]["journal"]["name"],
            account_meta[aid]["acc_name"],
        ),
    )

    rs = ReportSheet("Profit & Loss", n_text=3, n_val=n)
    rs.write_title("Profit & Loss")
    rs.write_generated()
    rs.write_blank()
    rs.write_period_header("For the 6 months ending:")
    rs.write_headers(["Journal", "Account", "Account Name"], labels)
    rs.set_col_widths([20, 24, 32] + [14] * n)

    current_atype: str | None = None
    current_is_debit: bool = False
    section_data_start: int = rs.row
    income_subtotal_rows: list[int] = []
    expense_subtotal_rows: list[int] = []

    def flush_section() -> None:
        if current_atype is None:
            return
        subtotal = rs.write_subtotal_row(f"Total {current_atype}", section_data_start)
        if current_is_debit:
            expense_subtotal_rows.append(subtotal)
        else:
            income_subtotal_rows.append(subtotal)
        rs.write_blank()

    for aid in ordered:
        meta = account_meta[aid]
        atype = meta["atype_name"]
        is_debit: bool = account_meta[aid].get("debit_account", False)

        if atype != current_atype:
            flush_section()
            current_atype = atype
            current_is_debit = is_debit
            rs.write_section_header(atype)
            section_data_start = rs.row

        rs.write_data_row(
            [meta["journal"]["name"], meta["acc_name"], meta["description"]],
            amounts[aid],
        )

    flush_section()

    rs.write_signed_ref_row("Net Income", add_rows=income_subtotal_rows, sub_rows=expense_subtotal_rows, fill=FILL_SUBTOTAL)
    rs.save(path)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


def cmd_logout(args: argparse.Namespace) -> None:
    session = load_session()
    effective_url = args.url or session.get("base_url") or DEFAULT_BASE_URL

    if session.get("session_id"):
        with httpx.Client(
            base_url=effective_url,
            cookies={"session_id": session["session_id"]},
        ) as client:
            client.post("/api/auth/logout")

    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
    print("Logged out.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lms",
        description="LMS command-line client",
    )
    parser.add_argument(
        "--url",
        default=None,
        metavar="URL",
        help=f"Base URL of the LMS server (default: {DEFAULT_BASE_URL})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # balance-sheet command
    bs = subparsers.add_parser(
        "balance-sheet",
        help="Export balance sheet to Excel",
    )
    bs.add_argument("--year", type=int, default=None, help="Report year (default: current year)")
    bs.add_argument("--month", type=int, default=None, help="Report month 1-12 (default: current month)")
    bs.add_argument("--periods", type=int, default=3, metavar="N", help="Number of annual periods (default: 3)")
    bs.add_argument("--output", "-o", default=None, metavar="FILE", help="Output .xlsx file (default: balance_sheet_YYYY_MM.xlsx)")
    bs.set_defaults(func=cmd_balance_sheet)

    # profit-loss command
    pl = subparsers.add_parser(
        "profit-loss",
        help="Export multi-period profit & loss to Excel",
    )
    pl.add_argument("--year", type=int, default=None, help="Anchor year (default: prior month's year)")
    pl.add_argument("--month", type=int, default=None, help="Anchor month 1-12 (default: prior month)")
    pl.add_argument("--years", type=int, default=2, metavar="N", help="Number of years of half-periods (default: 2 → 4 columns)")
    pl.add_argument("--output", "-o", default=None, metavar="FILE", help="Output .xlsx file (default: profit_loss_YYYY_MM.xlsx)")
    pl.set_defaults(func=cmd_profit_loss)

    # logout command
    lo = subparsers.add_parser("logout", help="Clear saved session")
    lo.set_defaults(func=cmd_logout)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
