#!/usr/bin/env bash
# psql.sh - Open a psql prompt connected to the LMS database as lms_owner.
#
# Usage:
#   DB_HOST=your-host DB_OWNER_PASSWORD=secret ./scripts/psql.sh
#
# Environment variables:
#   DB_HOST           - PostgreSQL host (required)
#   DB_PORT           - PostgreSQL port (default: 5432)
#   DB_NAME           - Database to connect to (default: lms)
#   DB_OWNER          - Role to connect as (default: lms_owner)
#   DB_OWNER_PASSWORD - Password for owner role (required)

set -euo pipefail

DB_HOST="${DB_HOST:?DB_HOST is required}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-lms}"
DB_OWNER="${DB_OWNER:-lms_owner}"
DB_OWNER_PASSWORD="${DB_OWNER_PASSWORD:?DB_OWNER_PASSWORD is required}"

exec docker run --rm -it \
    -e PGPASSWORD="$DB_OWNER_PASSWORD" \
    postgres:18-bookworm \
    psql \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_OWNER" \
    --no-password \
    "$DB_NAME"
