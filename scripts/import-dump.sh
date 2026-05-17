#!/usr/bin/env bash
# import-dump.sh - Restore a pg_dump archive into the LMS database.
#
# Supports both custom-format dumps (-Fc, the default for pg_dump) and
# plain SQL dumps (-Fp). Format is detected automatically by file extension:
#   *.dump, *.pgdump  -> pg_restore (custom format)
#   *.sql             -> psql (plain SQL)
#
# Connects as lms_owner (the database owner) so all restored objects are
# owned correctly without needing --no-owner rewriting.
#
# Usage:
#   DB_HOST=your-host DB_OWNER_PASSWORD=secret \
#     ./scripts/import-dump.sh /path/to/dump.dump
#
# Environment variables:
#   DB_HOST           - PostgreSQL host (required)
#   DB_PORT           - PostgreSQL port (default: 5432)
#   DB_NAME           - Target database (default: lms)
#   DB_OWNER          - Owner role to connect as (default: lms_owner)
#   DB_OWNER_PASSWORD - Password for owner role (required)

set -euo pipefail

DUMP_FILE="${1:?Usage: $0 /path/to/dump.dump}"

DB_HOST="${DB_HOST:?DB_HOST is required}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-lms}"
DB_OWNER="${DB_OWNER:-lms_owner}"
DB_OWNER_PASSWORD="${DB_OWNER_PASSWORD:?DB_OWNER_PASSWORD is required}"

if [[ ! -f "$DUMP_FILE" ]]; then
    echo "Error: file not found: $DUMP_FILE" >&2
    exit 1
fi

DUMP_ABS="$(realpath "$DUMP_FILE")"
DUMP_DIR="$(dirname "$DUMP_ABS")"
DUMP_BASENAME="$(basename "$DUMP_ABS")"

docker_psql() {
    docker run --rm \
        -e PGPASSWORD="$DB_OWNER_PASSWORD" \
        -v "$DUMP_DIR:/dump:ro" \
        postgres:18-bookworm \
        "$@" \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_OWNER" \
        --no-password \
        --dbname="$DB_NAME"
}

case "$DUMP_BASENAME" in
    *.sql)
        echo "==> Detected plain SQL dump, restoring with psql..."
        docker_psql psql --file="/dump/$DUMP_BASENAME"
        ;;
    *.dump|*.pgdump|*)
        echo "==> Detected custom-format dump, restoring with pg_restore..."
        docker_psql pg_restore \
            --verbose \
            --no-owner \
            --no-acl \
            --single-transaction \
            "/dump/$DUMP_BASENAME"
        ;;
esac

echo ""
echo "Done. Restored $DUMP_BASENAME -> $DB_OWNER@$DB_HOST:$DB_PORT/$DB_NAME"
