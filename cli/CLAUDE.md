# CLI

Standalone Python CLI for exporting LMS reports to Excel.

## Files

- `lms.py` — entry point: auth, account name resolution, one `cmd_*` function per subcommand, one `_write_*_xlsx` function per report
- `xlsx.py` — `ReportSheet` class: stateful row-cursor builder wrapping openpyxl; shared fill/font constants
- `requirements.txt` — `httpx`, `openpyxl`

## Key patterns

- `ensure_auth()` manages the session cookie (`~/.lms/session`); returns a ready `httpx.Client`
- `resolve_account_id(client, name)` fetches `GET /api/accounts` and resolves a name string (exact then substring) to a UUID
- Each command fetches JSON from the API, passes it to a `_write_*_xlsx()` helper, then prints the output path
- `ReportSheet` methods are called in top-to-bottom order; see the class docstring in `xlsx.py` for the full API
