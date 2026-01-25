#!/bin/bash
set -e

echo "Loading LMS schema files..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    \i /docker-entrypoint-initdb.d/sql/core.sql
    \i /docker-entrypoint-initdb.d/sql/authentication.sql
    \i /docker-entrypoint-initdb.d/sql/contacts.sql
    \i /docker-entrypoint-initdb.d/sql/databits.sql
    \i /docker-entrypoint-initdb.d/sql/lmshacc.sql
    \i /docker-entrypoint-initdb.d/sql/roscoe.sql
EOSQL

echo "Schema loaded successfully."

# Load development seed data if SEED_DEV_DATA is set
if [ "${SEED_DEV_DATA:-}" = "true" ]; then
    echo "Loading development seed data..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
        -f /docker-entrypoint-initdb.d/sql/seed_dev_data.sql
    echo "Seed data loaded successfully."
fi
