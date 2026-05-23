#!/usr/bin/env bash
# migrate-fts-simple-english.sh - Update FTS views to use both 'simple' and
# 'english' tsvector configs for better search recall.
#
# Covers: contacts.perfts_search, contacts.personas_calc, contacts.bits,
#         databits.perfts_search
#
# Replaces default-config (english-only) tsvectors with dual simple+english
# vectors. The backend query gains a prefix branch so partial typing
# ("Smi" matches "Smith") works.
#
# Safe to run multiple times (uses CREATE OR REPLACE VIEW).
#
# Usage:
#   DB_HOST=your-host DB_OWNER_PASSWORD=secret ./scripts/migrate-fts-simple-english.sh
#
# Environment variables:
#   DB_HOST           - PostgreSQL host (required)
#   DB_PORT           - PostgreSQL port (default: 5432)
#   DB_NAME           - Database name (default: lms)
#   DB_OWNER          - Role to connect as (default: lms_owner)
#   DB_OWNER_PASSWORD - Password for owner role (required)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="$SCRIPT_DIR/fts_simple_english.sql"

DB_HOST="${DB_HOST:?DB_HOST is required}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-lms}"
DB_OWNER="${DB_OWNER:-lms_owner}"
DB_OWNER_PASSWORD="${DB_OWNER_PASSWORD:?DB_OWNER_PASSWORD is required}"

echo "==> Applying FTS simple+english migration to $DB_OWNER@$DB_HOST:$DB_PORT/$DB_NAME"

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
    --file="/scripts/fts_simple_english.sql"

echo "Done."
