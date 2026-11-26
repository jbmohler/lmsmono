#!/usr/bin/env bash
# migrate-transaction-search-indexes.sh - Add indexes that make transaction
# search fast without a date horizon (full-text on payee/memo, trigram on
# tranref, trandate ordering, and splits.account_id).
#
# Indexes are built CONCURRENTLY, so writes are not blocked. Safe to run
# multiple times (uses IF NOT EXISTS). Requires permission to
# CREATE EXTENSION pg_trgm (or have it pre-installed by the DB provider).
#
# Usage:
#   DB_HOST=your-host DB_OWNER_PASSWORD=secret ./scripts/migrate-transaction-search-indexes.sh
#
# Environment variables:
#   DB_HOST           - PostgreSQL host (required)
#   DB_PORT           - PostgreSQL port (default: 5432)
#   DB_NAME           - Database name (default: lms)
#   DB_OWNER          - Role to connect as (default: lms_owner)
#   DB_OWNER_PASSWORD - Password for owner role (required)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DB_HOST="${DB_HOST:?DB_HOST is required}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-lms}"
DB_OWNER="${DB_OWNER:-lms_owner}"
DB_OWNER_PASSWORD="${DB_OWNER_PASSWORD:?DB_OWNER_PASSWORD is required}"

echo "==> Applying transaction search indexes to $DB_OWNER@$DB_HOST:$DB_PORT/$DB_NAME"

docker run --rm \
    -e PGPASSWORD="$DB_OWNER_PASSWORD" \
    -v "$SCRIPT_DIR:/scripts:ro" \
    postgres:18-bookworm \
    psql \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_OWNER" \
    --no-password \
    --dbname="$DB_NAME" \
    --file="/scripts/transaction_search_indexes.sql"

echo "Done."
