#!/usr/bin/env bash
# create-db.sh - Bootstrap the LMS database on a managed PostgreSQL instance.
#
# Creates:
#   lms_owner  - owns the database and all schema objects (used for migrations)
#   lms        - application user with DML-only privileges (no DDL)
#
# Usage:
#   DB_HOST=your-host DB_ADMIN_USER=postgres DB_ADMIN_PASSWORD=secret \
#     ./scripts/create-db.sh
#
# Environment variables:
#   DB_HOST           - PostgreSQL host (required)
#   DB_PORT           - PostgreSQL port (default: 5432)
#   DB_ADMIN_USER     - Admin user to connect as (default: postgres)
#                       GCP: postgres  |  DigitalOcean: doadmin
#   DB_ADMIN_PASSWORD - Admin user password (required)
#   DB_NAME           - Database to create (default: lms)
#   DB_OWNER          - Owner role to create (default: lms_owner)
#   DB_OWNER_PASSWORD - Password for owner role (required)
#   DB_APP_USER       - Application user to create (default: lms)
#   DB_APP_PASSWORD   - Password for app user (required)

set -euo pipefail

DB_HOST="${DB_HOST:?DB_HOST is required}"
DB_PORT="${DB_PORT:-5432}"
DB_ADMIN_USER="${DB_ADMIN_USER:-postgres}"
DB_ADMIN_PASSWORD="${DB_ADMIN_PASSWORD:?DB_ADMIN_PASSWORD is required}"
DB_NAME="${DB_NAME:-lms}"
DB_OWNER="${DB_OWNER:-lms_owner}"
DB_OWNER_PASSWORD="${DB_OWNER_PASSWORD:?DB_OWNER_PASSWORD is required}"
DB_APP_USER="${DB_APP_USER:-lms}"
DB_APP_PASSWORD="${DB_APP_PASSWORD:?DB_APP_PASSWORD is required}"

psql() {
    docker run --rm \
        -e PGPASSWORD="$DB_ADMIN_PASSWORD" \
        postgres:18-bookworm \
        psql \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_ADMIN_USER" \
        --no-password \
        "$@"
}

echo "==> Creating owner role: $DB_OWNER"
psql postgres <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_OWNER') THEN
    CREATE ROLE $DB_OWNER
      LOGIN
      PASSWORD '$DB_OWNER_PASSWORD'
      NOSUPERUSER NOCREATEDB NOCREATEROLE;
    RAISE NOTICE 'Role $DB_OWNER created.';
  ELSE
    RAISE NOTICE 'Role $DB_OWNER already exists, skipping.';
  END IF;
END
\$\$;
SQL

echo "==> Creating app user: $DB_APP_USER"
psql postgres <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_APP_USER') THEN
    CREATE ROLE $DB_APP_USER
      LOGIN
      PASSWORD '$DB_APP_PASSWORD'
      NOSUPERUSER NOCREATEDB NOCREATEROLE;
    RAISE NOTICE 'Role $DB_APP_USER created.';
  ELSE
    RAISE NOTICE 'Role $DB_APP_USER already exists, skipping.';
  END IF;
END
\$\$;
SQL

echo "==> Creating database: $DB_NAME (owner: $DB_OWNER)"
psql postgres <<SQL
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_OWNER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec
SQL

echo "==> Granting app user connect and usage privileges"
psql "$DB_NAME" <<SQL
-- Allow app user to connect
GRANT CONNECT ON DATABASE $DB_NAME TO $DB_APP_USER;

-- Allow app user to use the public schema
GRANT USAGE ON SCHEMA public TO $DB_APP_USER;

-- Grant DML on all current tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $DB_APP_USER;

-- Grant DML on future tables (created by lms_owner)
ALTER DEFAULT PRIVILEGES FOR ROLE $DB_OWNER IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $DB_APP_USER;

-- Grant usage on all current sequences
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO $DB_APP_USER;

-- Grant usage on future sequences
ALTER DEFAULT PRIVILEGES FOR ROLE $DB_OWNER IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO $DB_APP_USER;
SQL

echo ""
echo "Done. Connection strings:"
echo "  Owner (migrations): postgresql://$DB_OWNER:<password>@$DB_HOST:$DB_PORT/$DB_NAME"
echo "  App (server):       postgresql://$DB_APP_USER:<password>@$DB_HOST:$DB_PORT/$DB_NAME"
