-- migrate-pwhash-255.sql
-- Widens the user password/PIN hash columns from varchar(60) to varchar(255)
-- so they can hold an Argon2 hash (97 chars for the current parameters).
--
-- schema/sql/authentication.sql declared these as varchar(255) as of
-- 2026-05-18 (commit 7dc8edd), but no migration shipped with it, so any
-- database created before that date -- notably one restored from the legacy
-- LMS dump -- still has the 60-char columns. On those databases every
-- password write fails with:
--
--   psycopg.errors.StringDataRightTruncation:
--   value too long for type character varying(60)
--
-- ...which surfaces as a 500 from POST /api/auth/reset-password and from any
-- other path that sets a password.
--
-- Safe to run repeatedly: widening a varchar length is idempotent, preserves
-- existing values, and is a metadata-only change (no table rewrite).
--
-- Run as lms_owner:
--   DB_HOST=your-host DB_OWNER_PASSWORD=secret \
--     ./scripts/import-dump.sh schema/sql/migrate-pwhash-255.sql
-- Or paste into:
--   DB_HOST=your-host DB_OWNER_PASSWORD=secret ./scripts/psql.sh

BEGIN;

ALTER TABLE users ALTER COLUMN pwhash  TYPE varchar(255);
ALTER TABLE users ALTER COLUMN pinhash TYPE varchar(255);

COMMIT;
