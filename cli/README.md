# LMS CLI

Standalone Python client for exporting LMS reports to Excel and HTML. It talks to
a running LMS server over the same `/api/` routes the web frontend uses.

## Setup

```bash
pip install -r requirements.txt
python3 lms.py --help
```

The CLI is invoked as plain `lms` in `scripts/backup.sh`; put a wrapper or symlink
on your `PATH` if you want that shorthand.

## Authentication

The first command that needs the API prompts for a username and password, then
caches the session cookie in `~/.lms/session` (mode `0600`) along with the base
URL. Later runs reuse it and silently re-authenticate when it expires.

```bash
python3 lms.py --url https://lms.example.com balance-sheet   # sets the saved base URL
python3 lms.py logout                                        # clear the saved session
```

Because an expired session prompts interactively, run any scheduled job with a
session that is already valid — see the cron note below.

## Commands

| Command | Output |
|---|---|
| `balance-sheet` | Multi-period balance sheet (xlsx) |
| `balance-sheet-html` | Single-date balance sheet (html) |
| `profit-loss` | Multi-period P&L, rolling 6-month windows (xlsx) |
| `pl-transactions` | P&L transaction detail for a date range (xlsx) |
| `pl-transactions-html` | P&L transaction detail for a full year (html) |
| `transaction-detail-html` | Transaction register for a date range (html) |
| `payee-summary` | Payee spending summary for one account (xlsx) |
| `monthly` | The month-end report bundle, into one directory |
| `dumpyears` | Per-year report tree for archival/backup |
| `dump-tagged-contacts` | Contacts with a given tag, as text |

Date options default to the month that just ended, so month-end runs generally
need no arguments. Run `python3 lms.py <command> --help` for the full options.

## Month-end bundle

`monthly` runs the reports that belong together at the start of each month, all
anchored on the previous month. Three are always produced:

- Balance sheet as of the end of the month
- Detailed P&L transactions for the month
- Multi-period P&L — four rolling 6-month windows

Plus one payee summary per `--summary-account`, which is repeatable and defaults
to none. Account names are resolved exactly first, then by substring, so a
partial name works as long as it is unambiguous.

```bash
python3 lms.py monthly ~/reports/2026-06                     # the three standing reports
python3 lms.py monthly ~/reports --summary-account E_OFFER   # ... plus one payee summary
python3 lms.py monthly ~/reports \
    --summary-account E_OFFER --summary-account E_AUTO       # ... plus one per account
python3 lms.py monthly ~/reports --year 2026 --month 3
```

The output directory is created if it does not exist and defaults to the current
directory. A report that fails warns and the rest still run; the command exits
non-zero if any expected file is missing. Payee summaries are named after the
account, so several can share one directory.

### Running it on a schedule

The bundle is meant to be produced a few days into the month, once the prior
month's transactions have settled. To generate it at 6am on the 5th:

```cron
0 6 5 * * lms monthly /path/to/reports/$(date +\%Y-\%m) --summary-account E_OFFER
```

Note the escaped `%` characters — cron treats a bare `%` as a newline.

Cron cannot answer a login prompt, so the saved session in `~/.lms/session` must
be valid when the job fires; otherwise the run fails and writes nothing. Check
the output directory after the first scheduled run.
